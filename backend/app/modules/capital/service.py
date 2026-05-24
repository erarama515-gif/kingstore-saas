"""Capital service.

No own tables. Capital movements ARE journal entries with ``source="capital"``.
The summary reads back the Cash + Inventory + Owner-Capital + Owner-Drawings
balances and reports them as the four numbers shop owners actually want:

* liquid_cash      — balance of Cash (asset)
* inventory_value  — balance of Inventory (asset)
* total_capital    — liquid_cash + inventory_value (working capital)
* net_owner_equity — capital injected − drawings + retained
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import date as date_t
from decimal import Decimal
from typing import Optional

from sqlalchemy import desc, select

from app.core.pagination import paginate_offset
from app.extensions import db
from app.modules.accounting import service as acct
from app.modules.accounting.coa_seed import SystemAccount
from app.modules.accounting.models import JournalEntry
from app.modules.accounting.service import LineInput


log = logging.getLogger(__name__)


# --- Mutations ------------------------------------------------------------

def capital_inject(
    *,
    tenant_id: uuid.UUID,
    amount: Decimal,
    description: str,
    branch_id: Optional[uuid.UUID] = None,
    movement_date: Optional[date_t] = None,
    user_id: Optional[uuid.UUID] = None,
):
    """Owner adds cash. DR Cash / CR Owner's Capital."""
    mdate = movement_date or date_t.today()
    entry = acct.post_journal_entry(
        tenant_id=tenant_id,
        entry_date=mdate,
        branch_id=branch_id,
        source="capital",
        source_ref=None,
        reference="cap_in",
        description=description,
        posted_by_id=user_id,
        lines=[
            LineInput(
                account_id=acct.get_system_account_id(tenant_id, SystemAccount.CASH),
                debit=amount, description="Capital injection (cash in)",
            ),
            LineInput(
                account_id=acct.get_system_account_id(tenant_id, SystemAccount.OWNER_CAPITAL),
                credit=amount, description=description,
            ),
        ],
    )
    log.info("capital_in", extra={"tenant_id": str(tenant_id), "amount": str(amount)})
    return entry


def capital_withdraw(
    *,
    tenant_id: uuid.UUID,
    amount: Decimal,
    description: str,
    branch_id: Optional[uuid.UUID] = None,
    movement_date: Optional[date_t] = None,
    user_id: Optional[uuid.UUID] = None,
):
    """Owner pulls cash. DR Owner's Drawings / CR Cash."""
    mdate = movement_date or date_t.today()
    entry = acct.post_journal_entry(
        tenant_id=tenant_id,
        entry_date=mdate,
        branch_id=branch_id,
        source="capital",
        source_ref=None,
        reference="cap_out",
        description=description,
        posted_by_id=user_id,
        lines=[
            LineInput(
                account_id=acct.get_system_account_id(tenant_id, SystemAccount.OWNER_DRAWINGS),
                debit=amount, description=description,
            ),
            LineInput(
                account_id=acct.get_system_account_id(tenant_id, SystemAccount.CASH),
                credit=amount, description="Capital withdrawal (cash out)",
            ),
        ],
    )
    log.info("capital_out", extra={"tenant_id": str(tenant_id), "amount": str(amount)})
    return entry


# --- Reads ----------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class CapitalSummary:
    liquid_cash: Decimal
    inventory_value: Decimal
    total_working_capital: Decimal
    owner_capital: Decimal
    owner_drawings: Decimal
    retained_earnings: Decimal
    net_owner_equity: Decimal


def capital_summary(*, tenant_id: uuid.UUID) -> CapitalSummary:
    def bal(key: str) -> Decimal:
        try:
            aid = acct.get_system_account_id(tenant_id, key)
        except Exception:
            return Decimal("0")
        return acct.account_balance(tenant_id=tenant_id, account_id=aid).balance

    cash = bal(SystemAccount.CASH)
    inv = bal(SystemAccount.INVENTORY)
    cap = bal(SystemAccount.OWNER_CAPITAL)
    draw = bal(SystemAccount.OWNER_DRAWINGS)
    ret = bal(SystemAccount.RETAINED_EARNINGS)
    return CapitalSummary(
        liquid_cash=cash,
        inventory_value=inv,
        total_working_capital=(cash + inv).quantize(Decimal("0.01")),
        owner_capital=cap,
        owner_drawings=draw,
        retained_earnings=ret,
        net_owner_equity=(cap - draw + ret).quantize(Decimal("0.01")),
    )


def list_capital_movements(
    *, tenant_id: uuid.UUID, page: int, per_page: int
) -> dict:
    """Return paginated journal entries with ``source = "capital"``."""
    stmt = (
        select(JournalEntry)
        .where(
            JournalEntry.tenant_id == tenant_id,
            JournalEntry.source == "capital",
        )
        .order_by(desc(JournalEntry.entry_date), desc(JournalEntry.id))
    )
    return paginate_offset(db.session, stmt, page=page, per_page=per_page)
