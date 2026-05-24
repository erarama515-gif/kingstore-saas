"""Treasury service.

Cash position derives entirely from the ledger:

    cash_balance      = balance of CASH account
    bank_balance      = balance of BANK account
    today_cash_in     = sum of DEBITs against CASH for ``business_date``
    today_cash_out    = sum of CREDITs against CASH for ``business_date``

``close_day`` materializes the snapshot row for that business date at the
given branch, computes variance vs the cashier's count, and (optionally)
posts an adjustment journal entry for the variance.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import date as date_t, datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import desc, func, select
from werkzeug.exceptions import BadRequest, Conflict

from app.core.pagination import paginate_offset
from app.extensions import db
from app.modules.accounting import service as acct
from app.modules.accounting.coa_seed import SystemAccount
from app.modules.accounting.models import JournalEntry, JournalLine
from app.modules.accounting.service import LineInput
from app.modules.treasury.models import DayClose


log = logging.getLogger(__name__)


# --- Cash position --------------------------------------------------------

@dataclass(frozen=True, slots=True)
class CashPosition:
    cash_balance: Decimal
    bank_balance: Decimal
    today_cash_in: Decimal
    today_cash_out: Decimal
    today_net: Decimal
    business_date: date_t


def cash_position(
    *,
    tenant_id: uuid.UUID,
    business_date: Optional[date_t] = None,
    branch_id: Optional[uuid.UUID] = None,
) -> CashPosition:
    bd = business_date or date_t.today()
    session = db.session

    cash_id = acct.get_system_account_id(tenant_id, SystemAccount.CASH)
    try:
        bank_id = acct.get_system_account_id(tenant_id, SystemAccount.BANK)
    except BadRequest:
        bank_id = None

    cash_bal = acct.account_balance(
        tenant_id=tenant_id, account_id=cash_id, branch_id=branch_id
    ).balance
    bank_bal = (
        acct.account_balance(
            tenant_id=tenant_id, account_id=bank_id, branch_id=branch_id
        ).balance
        if bank_id else Decimal("0")
    )

    # Today's cash movement (debits in, credits out) — branch-filtered if given
    stmt = (
        select(
            func.coalesce(func.sum(JournalLine.debit), 0),
            func.coalesce(func.sum(JournalLine.credit), 0),
        )
        .select_from(JournalLine)
        .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
        .where(
            JournalLine.tenant_id == tenant_id,
            JournalLine.account_id == cash_id,
            JournalEntry.entry_date == bd,
        )
    )
    if branch_id is not None:
        stmt = stmt.where(JournalEntry.branch_id == branch_id)
    dr, cr = session.execute(stmt).one()
    dr, cr = Decimal(dr), Decimal(cr)

    return CashPosition(
        cash_balance=cash_bal,
        bank_balance=bank_bal,
        today_cash_in=dr,
        today_cash_out=cr,
        today_net=(dr - cr).quantize(Decimal("0.01")),
        business_date=bd,
    )


# --- Close day -----------------------------------------------------------

def close_day(
    *,
    tenant_id: uuid.UUID,
    branch_id: uuid.UUID,
    counted_cash: Decimal,
    business_date: Optional[date_t] = None,
    notes: Optional[str] = None,
    closed_by_id: Optional[uuid.UUID] = None,
) -> DayClose:
    """Snapshot the day's cash at a branch.

    If ``counted_cash != expected_cash``, the variance is recorded but no
    automatic journal adjustment is posted — the variance is a real-world
    discrepancy that should be investigated (the cashier or owner posts a
    manual adjustment through Accounting once they understand the cause).
    """
    session = db.session
    bd = business_date or date_t.today()

    # Conflict: one close per (tenant, branch, day)
    existing = session.execute(
        select(DayClose).where(
            DayClose.tenant_id == tenant_id,
            DayClose.branch_id == branch_id,
            DayClose.business_date == bd,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise Conflict(f"Day {bd} is already closed for this branch.")

    cash_id = acct.get_system_account_id(tenant_id, SystemAccount.CASH)
    # Opening = balance up to bd-1; today's in/out from today's lines
    from datetime import timedelta
    opening = acct.account_balance(
        tenant_id=tenant_id,
        account_id=cash_id,
        branch_id=branch_id,
        date_to=bd - timedelta(days=1),
    ).balance

    stmt = (
        select(
            func.coalesce(func.sum(JournalLine.debit), 0),
            func.coalesce(func.sum(JournalLine.credit), 0),
        )
        .select_from(JournalLine)
        .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
        .where(
            JournalLine.tenant_id == tenant_id,
            JournalLine.account_id == cash_id,
            JournalEntry.entry_date == bd,
            JournalEntry.branch_id == branch_id,
        )
    )
    dr, cr = session.execute(stmt).one()
    dr, cr = Decimal(dr), Decimal(cr)
    expected = (opening + dr - cr).quantize(Decimal("0.01"))
    variance = (counted_cash - expected).quantize(Decimal("0.01"))

    close = DayClose(
        tenant_id=tenant_id,
        branch_id=branch_id,
        business_date=bd,
        opening_cash=opening.quantize(Decimal("0.01")),
        cash_in=dr,
        cash_out=cr,
        expected_cash=expected,
        counted_cash=counted_cash,
        variance=variance,
        notes=notes,
        closed_by_id=closed_by_id,
        closed_at=datetime.now(timezone.utc),
    )
    session.add(close)
    session.flush()
    log.info(
        "day_closed",
        extra={
            "tenant_id": str(tenant_id),
            "branch_id": str(branch_id),
            "business_date": bd.isoformat(),
            "expected": str(expected),
            "counted": str(counted_cash),
            "variance": str(variance),
        },
    )
    return close


def day_snapshot(
    *, tenant_id: uuid.UUID, branch_id: uuid.UUID, business_date: date_t
) -> Optional[DayClose]:
    return db.session.execute(
        select(DayClose).where(
            DayClose.tenant_id == tenant_id,
            DayClose.branch_id == branch_id,
            DayClose.business_date == business_date,
        )
    ).scalar_one_or_none()


def list_day_closes(
    *,
    tenant_id: uuid.UUID,
    branch_id: Optional[uuid.UUID] = None,
    page: int = 1,
    per_page: int = 25,
) -> dict:
    stmt = (
        select(DayClose)
        .where(DayClose.tenant_id == tenant_id)
        .order_by(desc(DayClose.business_date))
    )
    if branch_id is not None:
        stmt = stmt.where(DayClose.branch_id == branch_id)
    return paginate_offset(db.session, stmt, page=page, per_page=per_page)
