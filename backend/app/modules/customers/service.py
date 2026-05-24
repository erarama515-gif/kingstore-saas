"""Customers service.

CRUD + POS-shaped lookups + AR-aware balance / statement reads.

Accounting integration
======================
* On create with ``opening_balance > 0``, post a journal entry:
    DR Accounts Receivable (tagged with this customer)
    CR Owner's Capital
  This makes the opening AR auditable and immediately visible in trial
  balance + customer balance.
* The balance / statement reads compute from the journal lines tagged
  with this customer — no fragile cache. The cached ``debt_cached`` on
  the row is for fast list rendering only; we re-sync it whenever the
  authoritative balance is computed.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import asc, select
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import Conflict, NotFound

from app.core.pagination import paginate_offset
from app.extensions import db
from app.modules.accounting import service as acct
from app.modules.accounting.coa_seed import SystemAccount
from app.modules.accounting.models import JournalEntry, JournalLine
from app.modules.accounting.service import LineInput
from app.modules.customers import repository as repo
from app.modules.customers.models import Customer
from app.modules.customers.schemas import CustomerCreate, CustomerUpdate


log = logging.getLogger(__name__)


# --- Create -----------------------------------------------------------------

def create_customer(
    *, tenant_id: uuid.UUID, payload: CustomerCreate,
    user_id: Optional[uuid.UUID] = None,
) -> Customer:
    """Insert a customer. Optionally post an opening AR balance.

    Raises:
        Conflict: phone or email already used by another customer.
    """
    session = db.session

    if payload.phone and repo.phone_taken(session, tenant_id=tenant_id, phone=payload.phone):
        raise Conflict(f"Phone '{payload.phone}' is already used by another customer.")
    if payload.email and repo.email_taken(session, tenant_id=tenant_id, email=str(payload.email)):
        raise Conflict(f"Email '{payload.email}' is already used by another customer.")

    customer = Customer(
        tenant_id=tenant_id,
        name=payload.name.strip(),
        name_ar=(payload.name_ar.strip() if payload.name_ar else None),
        phone=(payload.phone.strip() if payload.phone else None),
        email=(str(payload.email) if payload.email else None),
        address=payload.address,
        notes=payload.notes,
        is_active=True,
    )

    try:
        repo.add(session, customer)
    except IntegrityError as exc:
        session.rollback()
        raise Conflict("Customer phone or email collided; please retry.") from exc

    # Opening AR balance — post one journal entry tagged with this customer.
    if payload.opening_balance > 0:
        amt = payload.opening_balance.quantize(Decimal("0.01"))
        when = payload.opening_balance_date or date.today()
        acct.post_journal_entry(
            tenant_id=tenant_id,
            entry_date=when,
            source="customer_opening",
            source_ref=f"customer:{customer.id}",
            reference="Opening AR balance",
            description=f"Opening AR for {customer.name}",
            posted_by_id=user_id,
            lines=[
                LineInput(
                    account_id=acct.get_system_account_id(tenant_id, SystemAccount.AR),
                    debit=amt,
                    customer_id=customer.id,
                    description=f"Opening AR: {customer.name}",
                ),
                LineInput(
                    account_id=acct.get_system_account_id(tenant_id, SystemAccount.OWNER_CAPITAL),
                    credit=amt,
                    description="Counterparty: owner capital",
                ),
            ],
        )
        # Sync cache so the row list shows it immediately.
        customer.debt_cached = amt
        session.flush()

    log.info(
        "customer_created",
        extra={
            "tenant_id": str(tenant_id),
            "customer_id": str(customer.id),
            "phone": customer.phone,
            "opening_balance": str(payload.opening_balance),
        },
    )
    return customer


# --- Read -------------------------------------------------------------------

def get_customer(*, tenant_id: uuid.UUID, customer_id: uuid.UUID) -> Customer:
    c = repo.get_by_id(db.session, customer_id)
    if c is None or c.tenant_id != tenant_id or c.deleted_at is not None:
        raise NotFound("Customer not found.")
    return c


def list_customers(
    *,
    tenant_id: uuid.UUID,
    page: int,
    per_page: int,
    search: Optional[str] = None,
    only_active: bool = True,
    only_with_debt: bool = False,
) -> dict:
    stmt = repo.list_query(
        tenant_id=tenant_id,
        search=search,
        only_active=only_active,
        only_with_debt=only_with_debt,
    )
    return paginate_offset(db.session, stmt, page=page, per_page=per_page)


def quick_lookup(
    *, tenant_id: uuid.UUID, query: str, limit: int = 10
) -> list[Customer]:
    """POS-shaped lookup. Returns up to ``limit`` matches; empty list ok."""
    q = (query or "").strip()
    if not q:
        return []
    stmt = repo.quick_lookup_query(tenant_id=tenant_id, query=q, limit=limit)
    return list(db.session.execute(stmt).scalars().all())


def find_or_create_walkin(
    *, tenant_id: uuid.UUID, name: str, phone: Optional[str],
) -> Customer:
    """Used by the POS when a sale references a customer that may not exist.

    Lookup priority: phone (if given) → name. Creates a new row if no hit.
    Caller commits.
    """
    session = db.session
    if phone:
        existing = repo.get_by_phone(session, tenant_id=tenant_id, phone=phone.strip())
        if existing is not None:
            return existing

    # No phone match → try exact name (case-insensitive)
    from sqlalchemy import func as sa_func
    stmt = select(Customer).where(
        Customer.tenant_id == tenant_id,
        Customer.deleted_at.is_(None),
        sa_func.lower(Customer.name) == name.strip().lower(),
    )
    if not phone:
        stmt = stmt.where(Customer.phone.is_(None))
    existing = session.execute(stmt).scalar_one_or_none()
    if existing is not None:
        # If the existing row has no phone but caller now has one, attach it.
        if phone and not existing.phone and not repo.phone_taken(
            session, tenant_id=tenant_id, phone=phone, exclude_id=existing.id
        ):
            existing.phone = phone.strip()
        return existing

    new_customer = Customer(
        tenant_id=tenant_id,
        name=name.strip(),
        phone=(phone.strip() if phone else None),
        is_active=True,
    )
    return repo.add(session, new_customer)


# --- Update -----------------------------------------------------------------

def update_customer(
    *, tenant_id: uuid.UUID, customer_id: uuid.UUID, payload: CustomerUpdate
) -> Customer:
    session = db.session
    customer = get_customer(tenant_id=tenant_id, customer_id=customer_id)
    fields = payload.model_dump(exclude_unset=True)

    new_phone = fields.get("phone")
    if new_phone is not None and new_phone != customer.phone:
        if new_phone and repo.phone_taken(
            session, tenant_id=tenant_id, phone=new_phone, exclude_id=customer.id
        ):
            raise Conflict(f"Phone '{new_phone}' is already used by another customer.")

    new_email = fields.get("email")
    if new_email is not None and new_email != customer.email:
        if new_email and repo.email_taken(
            session, tenant_id=tenant_id, email=str(new_email), exclude_id=customer.id
        ):
            raise Conflict(f"Email '{new_email}' is already used by another customer.")

    for key, value in fields.items():
        if key == "email" and value is not None:
            value = str(value)
        setattr(customer, key, value)

    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise Conflict("Customer update violated a uniqueness constraint.") from exc
    return customer


# --- Delete (soft) ----------------------------------------------------------

def delete_customer(*, tenant_id: uuid.UUID, customer_id: uuid.UUID) -> None:
    customer = get_customer(tenant_id=tenant_id, customer_id=customer_id)
    customer.deleted_at = datetime.now(timezone.utc)
    customer.is_active = False
    db.session.flush()
    log.info("customer_deleted", extra={"customer_id": str(customer.id)})


# --- Balance (live from ledger) --------------------------------------------

@dataclass(frozen=True, slots=True)
class CustomerBalance:
    customer_id: uuid.UUID
    debt: Decimal              # net AR
    total_spent: Decimal
    visits_count: int
    last_txn_at: Optional[datetime]


def customer_balance(
    *, tenant_id: uuid.UUID, customer_id: uuid.UUID
) -> CustomerBalance:
    """Authoritative balance computed from the journal ledger.

    Reads sum(debit) - sum(credit) over AR-account lines tagged with this
    customer. Also re-syncs the cache so the next list call shows the
    correct number.
    """
    session = db.session
    customer = get_customer(tenant_id=tenant_id, customer_id=customer_id)

    ar_account_id = acct.get_system_account_id(tenant_id, SystemAccount.AR)
    from sqlalchemy import func as sa_func
    debit, credit = session.execute(
        select(
            sa_func.coalesce(sa_func.sum(JournalLine.debit), 0),
            sa_func.coalesce(sa_func.sum(JournalLine.credit), 0),
        ).where(
            JournalLine.tenant_id == tenant_id,
            JournalLine.account_id == ar_account_id,
            JournalLine.customer_id == customer_id,
        )
    ).one()
    debt = (Decimal(debit) - Decimal(credit)).quantize(Decimal("0.01"))

    # Re-sync cache (idempotent)
    if customer.debt_cached != debt:
        customer.debt_cached = debt
        session.flush()

    return CustomerBalance(
        customer_id=customer.id,
        debt=debt,
        total_spent=customer.total_spent_cached,
        visits_count=customer.visits_count,
        last_txn_at=customer.last_txn_at,
    )


# --- Statement (transaction history) ---------------------------------------

def customer_statement(
    *,
    tenant_id: uuid.UUID,
    customer_id: uuid.UUID,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict:
    """Account statement = chronological AR ledger for this customer with
    running balance. Returns a dict shaped for the response schema.
    """
    session = db.session
    customer = get_customer(tenant_id=tenant_id, customer_id=customer_id)
    ar_account_id = acct.get_system_account_id(tenant_id, SystemAccount.AR)

    # Opening balance = sum BEFORE date_from
    opening = Decimal("0")
    if date_from is not None:
        from sqlalchemy import func as sa_func
        op_dr, op_cr = session.execute(
            select(
                sa_func.coalesce(sa_func.sum(JournalLine.debit), 0),
                sa_func.coalesce(sa_func.sum(JournalLine.credit), 0),
            )
            .select_from(JournalLine)
            .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
            .where(
                JournalLine.tenant_id == tenant_id,
                JournalLine.account_id == ar_account_id,
                JournalLine.customer_id == customer_id,
                JournalEntry.entry_date < date_from,
            )
        ).one()
        opening = (Decimal(op_dr) - Decimal(op_cr)).quantize(Decimal("0.01"))

    # In-range lines
    stmt = (
        select(JournalLine, JournalEntry)
        .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
        .where(
            JournalLine.tenant_id == tenant_id,
            JournalLine.account_id == ar_account_id,
            JournalLine.customer_id == customer_id,
        )
        .order_by(asc(JournalEntry.entry_date), asc(JournalEntry.posted_at), asc(JournalLine.id))
    )
    if date_from is not None:
        stmt = stmt.where(JournalEntry.entry_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(JournalEntry.entry_date <= date_to)

    rows = session.execute(stmt).all()
    running = opening
    lines = []
    for line, entry in rows:
        running = (running + Decimal(line.debit) - Decimal(line.credit)).quantize(Decimal("0.01"))
        lines.append({
            "journal_entry_id": entry.id,
            "entry_date": entry.entry_date,
            "source": entry.source,
            "reference": entry.reference,
            "description": entry.description,
            "debit": Decimal(line.debit),
            "credit": Decimal(line.credit),
            "running_balance": running,
        })

    return {
        "customer_id": customer.id,
        "customer_name": customer.name,
        "opening_balance": opening,
        "closing_balance": running,
        "lines": lines,
    }
