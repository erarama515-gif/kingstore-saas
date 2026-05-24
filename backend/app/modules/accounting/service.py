"""Accounting service — the only public surface of the ledger.

Other modules call ``post_journal_entry(...)`` to record financial facts.
They never insert into ``journal_entries`` or ``journal_lines`` directly.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import date as date_t, datetime, timezone
from decimal import Decimal
from typing import Iterable, Optional

from flask import g
from werkzeug.exceptions import BadRequest, NotFound

from app.extensions import db
from app.modules.accounting import repository as repo
from app.modules.accounting.models import (
    Account,
    AccountType,
    JournalEntry,
    JournalLine,
)


log = logging.getLogger(__name__)


# --- Input dataclass (decoupled from Pydantic) ------------------------------

@dataclass(frozen=True, slots=True)
class LineInput:
    account_id: uuid.UUID
    debit: Decimal = Decimal("0")
    credit: Decimal = Decimal("0")
    description: Optional[str] = None
    # Counterparty tags. Set on AR lines (customer_id) and AP lines
    # (supplier_id) so per-customer/supplier balances come from the ledger.
    customer_id: Optional[uuid.UUID] = None
    supplier_id: Optional[uuid.UUID] = None


# --- Posting ----------------------------------------------------------------

def post_journal_entry(
    *,
    tenant_id: uuid.UUID,
    entry_date: date_t,
    lines: Iterable[LineInput],
    branch_id: Optional[uuid.UUID] = None,
    source: str = "manual",
    source_ref: Optional[str] = None,
    reference: Optional[str] = None,
    description: Optional[str] = None,
    posted_by_id: Optional[uuid.UUID] = None,
) -> JournalEntry:
    """Atomically post a balanced double-entry journal entry.

    Validation:
        * ≥ 2 lines
        * each line: debit XOR credit > 0; both >= 0
        * Σ debit == Σ credit (to the cent)
        * all account ids belong to this tenant
        * all accounts are active

    Raises:
        BadRequest: any validation failure.

    The caller is responsible for the surrounding ``db.session.commit()``.
    Posting itself does NOT commit — that's intentional so callers can chain
    multiple posts (and the original business mutation) in one transaction.
    """
    session = db.session
    line_list = list(lines)
    if len(line_list) < 2:
        raise BadRequest("Journal entry must have at least 2 lines.")

    total_debit = Decimal("0")
    total_credit = Decimal("0")
    for li in line_list:
        if li.debit < 0 or li.credit < 0:
            raise BadRequest("Line amounts must be non-negative.")
        dr_pos = li.debit > 0
        cr_pos = li.credit > 0
        if dr_pos == cr_pos:
            raise BadRequest(
                "Each line must have exactly one of debit or credit > 0."
            )
        total_debit += li.debit
        total_credit += li.credit

    if total_debit != total_credit:
        raise BadRequest(
            f"Entry not balanced: debits={total_debit}, credits={total_credit}."
        )
    if total_debit == 0:
        raise BadRequest("Entry total is zero.")

    # All accounts in one query — fail fast on unknown / cross-tenant ids
    account_ids = [li.account_id for li in line_list]
    accounts = repo.get_accounts_by_ids(session, tenant_id=tenant_id, ids=account_ids)
    missing = [aid for aid in account_ids if aid not in accounts]
    if missing:
        raise BadRequest(f"Unknown or cross-tenant accounts: {missing}")
    inactive = [a.code for a in accounts.values() if not a.is_active]
    if inactive:
        raise BadRequest(f"Inactive accounts cannot be posted to: {inactive}")

    entry = JournalEntry(
        tenant_id=tenant_id,
        branch_id=branch_id,
        entry_date=entry_date,
        source=source,
        source_ref=source_ref,
        reference=reference,
        description=description,
        posted_at=datetime.now(timezone.utc),
        posted_by_id=posted_by_id,
    )
    session.add(entry)
    session.flush()  # need entry.id for the lines

    for li in line_list:
        session.add(
            JournalLine(
                tenant_id=tenant_id,
                entry_id=entry.id,
                account_id=li.account_id,
                debit=li.debit,
                credit=li.credit,
                description=li.description,
                customer_id=li.customer_id,
                supplier_id=li.supplier_id,
            )
        )
    session.flush()

    log.info(
        "journal_entry_posted",
        extra={
            "tenant_id": str(tenant_id),
            "entry_id": str(entry.id),
            "source": source,
            "source_ref": source_ref,
            "total": str(total_debit),
            "lines": len(line_list),
        },
    )
    return entry


def reverse_journal_entry(
    *,
    tenant_id: uuid.UUID,
    entry_id: uuid.UUID,
    reason: str,
    reversal_date: Optional[date_t] = None,
    posted_by_id: Optional[uuid.UUID] = None,
) -> JournalEntry:
    """Post a reversal of an existing entry.

    The reversal entry inverts every line (debits become credits and vice
    versa) and links to the original via ``reverses_id``. The original
    remains in place — this preserves the audit trail.

    Raises:
        NotFound: original entry missing or belongs to another tenant.
        BadRequest: original is itself a reversal, or already reversed.
    """
    session = db.session
    original = repo.get_journal_entry(session, entry_id)
    if original is None or original.tenant_id != tenant_id:
        raise NotFound("Journal entry not found.")
    if original.reverses_id is not None:
        raise BadRequest("Cannot reverse a reversal entry.")
    # Detect prior reversal of this entry
    already = session.query(JournalEntry).filter(
        JournalEntry.tenant_id == tenant_id,
        JournalEntry.reverses_id == original.id,
    ).first()
    if already is not None:
        raise BadRequest("Entry has already been reversed.")

    inverted = [
        LineInput(
            account_id=l.account_id,
            debit=l.credit,
            credit=l.debit,
            description=l.description,
            customer_id=l.customer_id,
            supplier_id=l.supplier_id,
        )
        for l in original.lines
    ]

    reversal = post_journal_entry(
        tenant_id=tenant_id,
        entry_date=reversal_date or original.entry_date,
        lines=inverted,
        branch_id=original.branch_id,
        source="reversal",
        source_ref=f"reversal-of:{original.id}",
        reference=original.reference,
        description=f"Reversal: {reason}",
        posted_by_id=posted_by_id,
    )
    reversal.reverses_id = original.id
    session.flush()
    log.info(
        "journal_entry_reversed",
        extra={
            "tenant_id": str(tenant_id),
            "original_id": str(original.id),
            "reversal_id": str(reversal.id),
            "reason": reason,
        },
    )
    return reversal


# --- Read services ----------------------------------------------------------

@dataclass(frozen=True, slots=True)
class AccountBalance:
    account_id: uuid.UUID
    debit_total: Decimal
    credit_total: Decimal
    balance: Decimal  # signed on the account's natural side


def account_balance(
    *,
    tenant_id: uuid.UUID,
    account_id: uuid.UUID,
    branch_id: Optional[uuid.UUID] = None,
    date_from: Optional[date_t] = None,
    date_to: Optional[date_t] = None,
) -> AccountBalance:
    """Net balance for one account.

    Returned ``balance`` is positive on the account's natural side:
        * asset / expense: debit - credit
        * liability / equity / revenue: credit - debit
    A negative balance therefore means the account is "in the wrong direction"
    which is usually a red flag (e.g. cash going negative) — UI can highlight.
    """
    session = db.session
    account = repo.get_account(session, account_id)
    if account is None or account.tenant_id != tenant_id:
        raise NotFound("Account not found.")

    debit, credit = repo.sum_lines_for_account(
        session,
        tenant_id=tenant_id,
        account_id=account_id,
        branch_id=branch_id,
        date_from=date_from,
        date_to=date_to,
    )
    if account.type.is_debit_positive:
        net = debit - credit
    else:
        net = credit - debit
    return AccountBalance(
        account_id=account_id,
        debit_total=debit,
        credit_total=credit,
        balance=net,
    )


@dataclass(frozen=True, slots=True)
class TrialBalanceLine:
    account: Account
    debit_total: Decimal
    credit_total: Decimal
    balance: Decimal


@dataclass(frozen=True, slots=True)
class TrialBalanceReport:
    lines: list[TrialBalanceLine]
    debit_grand_total: Decimal
    credit_grand_total: Decimal

    @property
    def is_balanced(self) -> bool:
        return self.debit_grand_total == self.credit_grand_total


def trial_balance(
    *,
    tenant_id: uuid.UUID,
    branch_id: Optional[uuid.UUID] = None,
    date_from: Optional[date_t] = None,
    date_to: Optional[date_t] = None,
) -> TrialBalanceReport:
    rows = repo.trial_balance_rows(
        db.session,
        tenant_id=tenant_id,
        branch_id=branch_id,
        date_from=date_from,
        date_to=date_to,
    )

    grand_dr = Decimal("0")
    grand_cr = Decimal("0")
    lines: list[TrialBalanceLine] = []
    for account, dr, cr in rows:
        grand_dr += dr
        grand_cr += cr
        if account.type.is_debit_positive:
            balance = dr - cr
        else:
            balance = cr - dr
        lines.append(
            TrialBalanceLine(
                account=account,
                debit_total=dr,
                credit_total=cr,
                balance=balance,
            )
        )
    return TrialBalanceReport(
        lines=lines,
        debit_grand_total=grand_dr,
        credit_grand_total=grand_cr,
    )


# --- Helpers for other modules ----------------------------------------------

def get_system_account_id(tenant_id: uuid.UUID, system_key: str) -> uuid.UUID:
    """Resolve a system_key to an account id for the current tenant.

    Used by ``sales`` / ``expenses`` / ``treasury`` to post entries without
    hardcoding account codes.

    Raises:
        BadRequest: tenant doesn't have an account with that system_key
            (typically means CoA wasn't seeded — bug in signup flow).
    """
    acct = repo.get_system_account(
        db.session, tenant_id=tenant_id, system_key=system_key
    )
    if acct is None:
        raise BadRequest(
            f"System account '{system_key}' not configured for this tenant."
        )
    return acct.id


def current_tenant_required() -> uuid.UUID:
    """Read ``g.tenant_id`` and fail clearly if missing."""
    tid = getattr(g, "tenant_id", None)
    if tid is None:
        raise BadRequest("Tenant context required.")
    return tid
