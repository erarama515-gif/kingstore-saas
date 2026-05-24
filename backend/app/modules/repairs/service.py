"""Repairs service.

On ``deliver``:
    DR Cash (or AR if is_paid=False) / CR Service Revenue
"""

from __future__ import annotations

import logging
import uuid
from datetime import date as date_t, datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import Select, desc, func, select
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import BadRequest, Conflict, NotFound

from app.core.pagination import paginate_offset
from app.extensions import db
from app.modules.accounting import service as acct
from app.modules.accounting.coa_seed import SystemAccount
from app.modules.accounting.service import LineInput
from app.modules.customers.models import Customer
from app.modules.repairs.models import RepairStatus, RepairTicket
from app.modules.repairs.schemas import RepairCreate, RepairDeliverRequest


log = logging.getLogger(__name__)


# --- Create ----------------------------------------------------------------

def create_ticket(
    *,
    tenant_id: uuid.UUID,
    payload: RepairCreate,
    technician_id: Optional[uuid.UUID] = None,
) -> RepairTicket:
    session = db.session
    if payload.customer_id is not None:
        cust = session.get(Customer, payload.customer_id)
        if cust is None or cust.tenant_id != tenant_id or cust.deleted_at is not None:
            raise NotFound("Customer not found.")
    for attempt in range(3):
        cnt = session.execute(
            select(func.count()).select_from(RepairTicket).where(
                RepairTicket.tenant_id == tenant_id
            )
        ).scalar_one()
        ticket_number = f"REP-{(cnt + 1 + attempt):06d}"
        ticket = RepairTicket(
            tenant_id=tenant_id,
            ticket_number=ticket_number,
            branch_id=payload.branch_id,
            customer_id=payload.customer_id,
            customer_name=payload.customer_name.strip(),
            customer_phone=payload.customer_phone,
            device_model=payload.device_model.strip(),
            imei=payload.imei,
            problem=payload.problem.strip(),
            estimated_cost=payload.estimated_cost,
            status=RepairStatus.received,
            date_in=date_t.today(),
            notes=payload.notes,
            technician_id=technician_id,
        )
        session.add(ticket)
        try:
            session.flush()
            log.info(
                "repair_created",
                extra={"tenant_id": str(tenant_id), "ticket_id": str(ticket.id), "no": ticket_number},
            )
            return ticket
        except IntegrityError:
            session.rollback()
            if attempt == 2:
                raise
    raise RuntimeError("unreachable")


# --- Status workflow ------------------------------------------------------

_TRANSITIONS = {
    RepairStatus.received: {RepairStatus.in_progress, RepairStatus.canceled},
    RepairStatus.in_progress: {RepairStatus.done, RepairStatus.canceled},
    RepairStatus.done: {RepairStatus.in_progress},  # send back if QA fails
    RepairStatus.delivered: set(),  # terminal
    RepairStatus.canceled: set(),
}


def update_status(
    *,
    tenant_id: uuid.UUID,
    ticket_id: uuid.UUID,
    new_status: str,
    notes: Optional[str] = None,
) -> RepairTicket:
    ticket = get_ticket(tenant_id=tenant_id, ticket_id=ticket_id)
    try:
        new = RepairStatus(new_status)
    except ValueError:
        raise BadRequest(f"Invalid status '{new_status}'.")
    if new not in _TRANSITIONS.get(ticket.status, set()):
        raise BadRequest(f"Cannot move {ticket.status.value} → {new.value}.")
    if new == RepairStatus.delivered:
        raise BadRequest("Use POST /repairs/{id}/deliver to deliver a ticket.")
    ticket.status = new
    if notes:
        ticket.notes = (ticket.notes or "") + f"\n[{new.value}] {notes}"
    db.session.flush()
    return ticket


# --- Deliver --------------------------------------------------------------

def deliver(
    *,
    tenant_id: uuid.UUID,
    ticket_id: uuid.UUID,
    payload: RepairDeliverRequest,
    user_id: Optional[uuid.UUID] = None,
) -> RepairTicket:
    """Finalize a repair: post Service Revenue journal entry and stamp the
    delivery date.

    The legacy app required ``status=done`` before delivery; we keep the same
    rule. From any other status (received, in_progress) delivery is blocked.
    """
    session = db.session
    ticket = get_ticket(tenant_id=tenant_id, ticket_id=ticket_id)
    if ticket.status == RepairStatus.delivered:
        raise Conflict("Ticket already delivered.")
    if ticket.status not in (RepairStatus.done, RepairStatus.received):
        # Allow "received → delivered" shortcut for trivial repairs.
        raise BadRequest(
            f"Cannot deliver a ticket in status '{ticket.status.value}'. "
            "Set it to 'done' first."
        )

    amount = payload.actual_cost or ticket.estimated_cost
    if amount <= 0:
        raise BadRequest("Delivery cost must be positive.")

    delivery_date = payload.delivery_date or date_t.today()
    cash_key = SystemAccount.CASH if payload.payment_method == "cash" else SystemAccount.BANK

    if payload.is_paid:
        lines = [
            LineInput(
                account_id=acct.get_system_account_id(tenant_id, cash_key),
                debit=amount,
                description=f"Repair payment ({payload.payment_method})",
            ),
            LineInput(
                account_id=acct.get_system_account_id(tenant_id, SystemAccount.SERVICE_REVENUE),
                credit=amount,
                description=f"Service revenue {ticket.ticket_number}",
            ),
        ]
    else:
        if ticket.customer_id is None:
            raise BadRequest(
                "Credit delivery (is_paid=False) requires the ticket to have a customer_id."
            )
        lines = [
            LineInput(
                account_id=acct.get_system_account_id(tenant_id, SystemAccount.AR),
                debit=amount,
                customer_id=ticket.customer_id,
                description=f"AR for repair {ticket.ticket_number}",
            ),
            LineInput(
                account_id=acct.get_system_account_id(tenant_id, SystemAccount.SERVICE_REVENUE),
                credit=amount,
                description=f"Service revenue {ticket.ticket_number}",
            ),
        ]

    entry = acct.post_journal_entry(
        tenant_id=tenant_id,
        entry_date=delivery_date,
        branch_id=ticket.branch_id,
        source="repair",
        source_ref=f"repair:{ticket.id}",
        reference=ticket.ticket_number,
        description=f"Repair delivery {ticket.ticket_number}",
        posted_by_id=user_id,
        lines=lines,
    )

    ticket.actual_cost = amount
    ticket.status = RepairStatus.delivered
    ticket.date_delivered = delivery_date
    ticket.delivered_at = datetime.now(timezone.utc)
    ticket.is_paid_on_delivery = payload.is_paid
    ticket.delivery_journal_entry_id = entry.id
    if payload.notes:
        ticket.notes = (ticket.notes or "") + f"\n[delivered] {payload.notes}"

    # Update customer cache
    if ticket.customer_id:
        cust = session.get(Customer, ticket.customer_id)
        if cust:
            if payload.is_paid:
                cust.total_spent_cached = (cust.total_spent_cached + amount).quantize(Decimal("0.01"))
            else:
                cust.debt_cached = (cust.debt_cached + amount).quantize(Decimal("0.01"))
            cust.last_txn_at = datetime.now(timezone.utc)

    session.flush()
    log.info(
        "repair_delivered",
        extra={
            "tenant_id": str(tenant_id),
            "ticket_id": str(ticket.id),
            "amount": str(amount),
            "is_paid": payload.is_paid,
        },
    )
    return ticket


# --- Reads ----------------------------------------------------------------

def get_ticket(*, tenant_id: uuid.UUID, ticket_id: uuid.UUID) -> RepairTicket:
    t = db.session.get(RepairTicket, ticket_id)
    if t is None or t.tenant_id != tenant_id or t.deleted_at is not None:
        raise NotFound("Repair ticket not found.")
    return t


def list_tickets(
    *,
    tenant_id: uuid.UUID,
    page: int,
    per_page: int,
    branch_id: Optional[uuid.UUID] = None,
    status: Optional[str] = None,
    customer_id: Optional[uuid.UUID] = None,
) -> dict:
    stmt: Select = (
        select(RepairTicket)
        .where(RepairTicket.tenant_id == tenant_id, RepairTicket.deleted_at.is_(None))
        .order_by(desc(RepairTicket.date_in), desc(RepairTicket.created_at))
    )
    if branch_id is not None:
        stmt = stmt.where(RepairTicket.branch_id == branch_id)
    if status is not None:
        stmt = stmt.where(RepairTicket.status == status)
    if customer_id is not None:
        stmt = stmt.where(RepairTicket.customer_id == customer_id)
    return paginate_offset(db.session, stmt, page=page, per_page=per_page)
