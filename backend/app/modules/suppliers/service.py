"""Suppliers service.

Mirrors the customers service, but AP-side: opening balance posts
DR Owner's Capital / CR AP (tagged with this supplier); balances are
credit-positive (AP is a liability).
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
from app.modules.suppliers import repository as repo
from app.modules.suppliers.models import Supplier
from app.modules.suppliers.schemas import SupplierCreate, SupplierUpdate


log = logging.getLogger(__name__)


# --- Create -----------------------------------------------------------------

def create_supplier(
    *, tenant_id: uuid.UUID, payload: SupplierCreate,
    user_id: Optional[uuid.UUID] = None,
) -> Supplier:
    session = db.session

    if payload.phone and repo.phone_taken(session, tenant_id=tenant_id, phone=payload.phone):
        raise Conflict(f"Phone '{payload.phone}' is already used by another supplier.")
    if payload.email and repo.email_taken(session, tenant_id=tenant_id, email=str(payload.email)):
        raise Conflict(f"Email '{payload.email}' is already used by another supplier.")

    supplier = Supplier(
        tenant_id=tenant_id,
        name=payload.name.strip(),
        name_ar=(payload.name_ar.strip() if payload.name_ar else None),
        phone=(payload.phone.strip() if payload.phone else None),
        email=(str(payload.email) if payload.email else None),
        contact_person=payload.contact_person,
        address=payload.address,
        notes=payload.notes,
        is_active=True,
    )

    try:
        repo.add(session, supplier)
    except IntegrityError as exc:
        session.rollback()
        raise Conflict("Supplier phone or email collided; please retry.") from exc

    if payload.opening_balance > 0:
        amt = payload.opening_balance.quantize(Decimal("0.01"))
        when = payload.opening_balance_date or date.today()
        acct.post_journal_entry(
            tenant_id=tenant_id,
            entry_date=when,
            source="supplier_opening",
            source_ref=f"supplier:{supplier.id}",
            reference="Opening AP balance",
            description=f"Opening AP for {supplier.name}",
            posted_by_id=user_id,
            lines=[
                LineInput(
                    account_id=acct.get_system_account_id(tenant_id, SystemAccount.OWNER_CAPITAL),
                    debit=amt,
                    description="Counterparty: owner capital",
                ),
                LineInput(
                    account_id=acct.get_system_account_id(tenant_id, SystemAccount.AP),
                    credit=amt,
                    supplier_id=supplier.id,
                    description=f"Opening AP: {supplier.name}",
                ),
            ],
        )
        supplier.payable_cached = amt
        session.flush()

    log.info(
        "supplier_created",
        extra={
            "tenant_id": str(tenant_id),
            "supplier_id": str(supplier.id),
            "opening_balance": str(payload.opening_balance),
        },
    )
    return supplier


# --- Read -------------------------------------------------------------------

def get_supplier(*, tenant_id: uuid.UUID, supplier_id: uuid.UUID) -> Supplier:
    s = repo.get_by_id(db.session, supplier_id)
    if s is None or s.tenant_id != tenant_id or s.deleted_at is not None:
        raise NotFound("Supplier not found.")
    return s


def list_suppliers(
    *,
    tenant_id: uuid.UUID,
    page: int,
    per_page: int,
    search: Optional[str] = None,
    only_active: bool = True,
    only_with_payable: bool = False,
) -> dict:
    stmt = repo.list_query(
        tenant_id=tenant_id,
        search=search,
        only_active=only_active,
        only_with_payable=only_with_payable,
    )
    return paginate_offset(db.session, stmt, page=page, per_page=per_page)


def quick_lookup(
    *, tenant_id: uuid.UUID, query: str, limit: int = 10
) -> list[Supplier]:
    q = (query or "").strip()
    if not q:
        return []
    stmt = repo.quick_lookup_query(tenant_id=tenant_id, query=q, limit=limit)
    return list(db.session.execute(stmt).scalars().all())


# --- Update -----------------------------------------------------------------

def update_supplier(
    *, tenant_id: uuid.UUID, supplier_id: uuid.UUID, payload: SupplierUpdate
) -> Supplier:
    session = db.session
    supplier = get_supplier(tenant_id=tenant_id, supplier_id=supplier_id)
    fields = payload.model_dump(exclude_unset=True)

    new_phone = fields.get("phone")
    if new_phone is not None and new_phone != supplier.phone:
        if new_phone and repo.phone_taken(
            session, tenant_id=tenant_id, phone=new_phone, exclude_id=supplier.id
        ):
            raise Conflict(f"Phone '{new_phone}' is already used by another supplier.")

    new_email = fields.get("email")
    if new_email is not None and new_email != supplier.email:
        if new_email and repo.email_taken(
            session, tenant_id=tenant_id, email=str(new_email), exclude_id=supplier.id
        ):
            raise Conflict(f"Email '{new_email}' is already used by another supplier.")

    for key, value in fields.items():
        if key == "email" and value is not None:
            value = str(value)
        setattr(supplier, key, value)

    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise Conflict("Supplier update violated a uniqueness constraint.") from exc
    return supplier


# --- Delete (soft) ----------------------------------------------------------

def delete_supplier(*, tenant_id: uuid.UUID, supplier_id: uuid.UUID) -> None:
    supplier = get_supplier(tenant_id=tenant_id, supplier_id=supplier_id)
    supplier.deleted_at = datetime.now(timezone.utc)
    supplier.is_active = False
    db.session.flush()


# --- Balance / statement (live from ledger) --------------------------------

@dataclass(frozen=True, slots=True)
class SupplierBalance:
    supplier_id: uuid.UUID
    payable: Decimal
    total_purchased: Decimal
    last_txn_at: Optional[datetime]


def supplier_balance(
    *, tenant_id: uuid.UUID, supplier_id: uuid.UUID
) -> SupplierBalance:
    """Authoritative AP balance computed from the journal ledger.

    AP is credit-positive (liability), so payable = SUM(credit) - SUM(debit).
    """
    session = db.session
    supplier = get_supplier(tenant_id=tenant_id, supplier_id=supplier_id)
    ap_account_id = acct.get_system_account_id(tenant_id, SystemAccount.AP)

    from sqlalchemy import func as sa_func
    debit, credit = session.execute(
        select(
            sa_func.coalesce(sa_func.sum(JournalLine.debit), 0),
            sa_func.coalesce(sa_func.sum(JournalLine.credit), 0),
        ).where(
            JournalLine.tenant_id == tenant_id,
            JournalLine.account_id == ap_account_id,
            JournalLine.supplier_id == supplier_id,
        )
    ).one()
    payable = (Decimal(credit) - Decimal(debit)).quantize(Decimal("0.01"))

    if supplier.payable_cached != payable:
        supplier.payable_cached = payable
        session.flush()

    return SupplierBalance(
        supplier_id=supplier.id,
        payable=payable,
        total_purchased=supplier.total_purchased_cached,
        last_txn_at=supplier.last_txn_at,
    )


def supplier_statement(
    *,
    tenant_id: uuid.UUID,
    supplier_id: uuid.UUID,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict:
    """AP statement: credit-positive running balance."""
    session = db.session
    supplier = get_supplier(tenant_id=tenant_id, supplier_id=supplier_id)
    ap_account_id = acct.get_system_account_id(tenant_id, SystemAccount.AP)

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
                JournalLine.account_id == ap_account_id,
                JournalLine.supplier_id == supplier_id,
                JournalEntry.entry_date < date_from,
            )
        ).one()
        opening = (Decimal(op_cr) - Decimal(op_dr)).quantize(Decimal("0.01"))

    stmt = (
        select(JournalLine, JournalEntry)
        .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
        .where(
            JournalLine.tenant_id == tenant_id,
            JournalLine.account_id == ap_account_id,
            JournalLine.supplier_id == supplier_id,
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
        # AP balance increases on credit, decreases on debit
        running = (running + Decimal(line.credit) - Decimal(line.debit)).quantize(Decimal("0.01"))
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
        "supplier_id": supplier.id,
        "supplier_name": supplier.name,
        "opening_balance": opening,
        "closing_balance": running,
        "lines": lines,
    }
