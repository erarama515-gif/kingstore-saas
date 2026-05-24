"""AR / AP aging helpers.

Aging bucket = how old the outstanding amount is, computed from the
journal entry date of the *origination* line, not its later payment.

For simplicity in MVP we use a per-counterparty net-balance bucketed by
the average date of unpaid origination — good enough for the dashboard.
A line-by-line "open invoices" aging that pairs payments to invoices
(FIFO match) is deferred to F11 reports.

Buckets (days): 0-30, 31-60, 61-90, 90+
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.accounting.coa_seed import SystemAccount
from app.modules.accounting.models import JournalEntry, JournalLine
from app.modules.accounting.repository import get_system_account


Side = Literal["ar", "ap"]


@dataclass(frozen=True, slots=True)
class AgingBucket:
    label: str
    min_days: int
    max_days: int | None  # None = open-ended


BUCKETS: tuple[AgingBucket, ...] = (
    AgingBucket("0-30",  0, 30),
    AgingBucket("31-60", 31, 60),
    AgingBucket("61-90", 61, 90),
    AgingBucket("90+",   91, None),
)


@dataclass(frozen=True, slots=True)
class AgingRow:
    counterparty_id: uuid.UUID
    counterparty_name: str
    buckets: dict[str, Decimal]  # label → amount
    total: Decimal


def _aging_for_side(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    side: Side,
    as_of: date,
) -> list[AgingRow]:
    """Compute aging rows for AR (side="ar") or AP (side="ap").

    Algorithm
    ---------
    For each counterparty:
      1. Read every line on the AR/AP account, with its entry date.
      2. Walk in chronological order, treating credits (for AR; debits for
         AP) as paying down the oldest outstanding amount first (FIFO).
      3. Whatever's left at the end is bucketed by the age of the oldest
         remaining originating entry.

    This is a single-pass O(n) per counterparty. For the MVP demo with
    handful of customers, plenty fast.
    """
    if side == "ar":
        account_key = SystemAccount.AR
        join_table = "customers"
        counter_attr = JournalLine.customer_id
    else:
        account_key = SystemAccount.AP
        join_table = "suppliers"
        counter_attr = JournalLine.supplier_id

    account = get_system_account(session, tenant_id=tenant_id, system_key=account_key)
    if account is None:
        return []

    # Pull all lines tagged with a counterparty up to as_of
    rows = session.execute(
        select(
            JournalLine.id,
            counter_attr,
            JournalLine.debit,
            JournalLine.credit,
            JournalEntry.entry_date,
        )
        .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
        .where(
            JournalLine.tenant_id == tenant_id,
            JournalLine.account_id == account.id,
            counter_attr.is_not(None),
            JournalEntry.entry_date <= as_of,
        )
        .order_by(counter_attr, JournalEntry.entry_date, JournalLine.id)
    ).all()

    # Group by counterparty
    by_party: dict[uuid.UUID, list[tuple]] = {}
    for line_id, party_id, dr, cr, entry_date in rows:
        by_party.setdefault(party_id, []).append((entry_date, Decimal(dr), Decimal(cr)))

    # Look up names in one query
    if by_party:
        from sqlalchemy import text
        name_rows = session.execute(
            text(
                f"SELECT id, name FROM {join_table} "
                f"WHERE tenant_id = :tid AND id IN :ids"
            ).bindparams(tid=tenant_id, ids=tuple(by_party.keys()))
        ).all()
    else:
        name_rows = []
    name_by_id = {r[0]: r[1] for r in name_rows}

    aging_rows: list[AgingRow] = []
    for party_id, party_lines in by_party.items():
        # FIFO match: collect originations (debits for AR, credits for AP),
        # and apply opposite-sign lines to the oldest open origination.
        # Each "open" is (entry_date, remaining_amount).
        opens: list[list] = []
        for entry_date, dr, cr in party_lines:
            origination = dr if side == "ar" else cr
            payment = cr if side == "ar" else dr
            if origination > 0:
                opens.append([entry_date, origination])
            if payment > 0:
                remaining = payment
                for o in opens:
                    if remaining <= 0:
                        break
                    if o[1] <= 0:
                        continue
                    take = min(o[1], remaining)
                    o[1] -= take
                    remaining -= take
                # Any payment > origination becomes a credit balance (overpaid).
                # For aging purposes we ignore it (overpayments age into the
                # 0-30 bucket as a "negative" — not modeled here for MVP).

        buckets = {b.label: Decimal("0") for b in BUCKETS}
        total = Decimal("0")
        for entry_date, remaining in opens:
            if remaining <= 0:
                continue
            age = (as_of - entry_date).days
            for b in BUCKETS:
                if b.max_days is None or age <= b.max_days:
                    if age >= b.min_days:
                        buckets[b.label] += remaining
                        total += remaining
                        break

        if total > 0:
            aging_rows.append(AgingRow(
                counterparty_id=party_id,
                counterparty_name=name_by_id.get(party_id, "(unknown)"),
                buckets={k: v.quantize(Decimal("0.01")) for k, v in buckets.items()},
                total=total.quantize(Decimal("0.01")),
            ))

    # Sort by total desc — biggest debtors / payables first
    aging_rows.sort(key=lambda r: r.total, reverse=True)
    return aging_rows


def ar_aging(
    session: Session, *, tenant_id: uuid.UUID, as_of: date | None = None
) -> list[AgingRow]:
    return _aging_for_side(session, tenant_id=tenant_id, side="ar", as_of=as_of or date.today())


def ap_aging(
    session: Session, *, tenant_id: uuid.UUID, as_of: date | None = None
) -> list[AgingRow]:
    return _aging_for_side(session, tenant_id=tenant_id, side="ap", as_of=as_of or date.today())
