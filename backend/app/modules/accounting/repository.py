"""Accounting data access.

Repositories return ORM objects or raw aggregates. No business rules here —
the service layer composes these into ``post_journal_entry`` etc.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional, Sequence

from sqlalchemy import Select, and_, func, select
from sqlalchemy.orm import Session

from app.modules.accounting.models import (
    Account,
    AccountType,
    JournalEntry,
    JournalLine,
)


# --- Accounts ---------------------------------------------------------------

def list_accounts(
    session: Session, *, tenant_id: uuid.UUID, only_active: bool = True
) -> list[Account]:
    stmt: Select[tuple[Account]] = (
        select(Account)
        .where(Account.tenant_id == tenant_id)
        .order_by(Account.code)
    )
    if only_active:
        stmt = stmt.where(Account.is_active.is_(True))
    return list(session.execute(stmt).scalars().all())


def get_account(session: Session, account_id: uuid.UUID) -> Optional[Account]:
    return session.get(Account, account_id)


def get_accounts_by_ids(
    session: Session, *, tenant_id: uuid.UUID, ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, Account]:
    if not ids:
        return {}
    rows = session.execute(
        select(Account).where(
            Account.tenant_id == tenant_id, Account.id.in_(list(ids))
        )
    ).scalars().all()
    return {a.id: a for a in rows}


def get_system_account(
    session: Session, *, tenant_id: uuid.UUID, system_key: str
) -> Optional[Account]:
    return session.execute(
        select(Account).where(
            Account.tenant_id == tenant_id,
            Account.system_key == system_key,
        )
    ).scalar_one_or_none()


# --- Journal entries --------------------------------------------------------

def get_journal_entry(
    session: Session, entry_id: uuid.UUID
) -> Optional[JournalEntry]:
    return session.get(JournalEntry, entry_id)


def list_entries_for_source(
    session: Session, *, tenant_id: uuid.UUID, source_ref: str
) -> list[JournalEntry]:
    return list(
        session.execute(
            select(JournalEntry).where(
                JournalEntry.tenant_id == tenant_id,
                JournalEntry.source_ref == source_ref,
            )
        ).scalars().all()
    )


# --- Aggregates -------------------------------------------------------------

def sum_lines_for_account(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    account_id: uuid.UUID,
    branch_id: Optional[uuid.UUID] = None,
    date_from=None,
    date_to=None,
) -> tuple[Decimal, Decimal]:
    """Return ``(sum_debit, sum_credit)`` for the lines of an account.

    The join with ``journal_entries`` lets us filter by date / branch — fields
    that live on the header, not the line.
    """
    stmt = (
        select(
            func.coalesce(func.sum(JournalLine.debit), 0),
            func.coalesce(func.sum(JournalLine.credit), 0),
        )
        .select_from(JournalLine)
        .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
        .where(
            JournalLine.tenant_id == tenant_id,
            JournalLine.account_id == account_id,
        )
    )
    if branch_id is not None:
        stmt = stmt.where(JournalEntry.branch_id == branch_id)
    if date_from is not None:
        stmt = stmt.where(JournalEntry.entry_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(JournalEntry.entry_date <= date_to)
    debit, credit = session.execute(stmt).one()
    return Decimal(debit), Decimal(credit)


def trial_balance_rows(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    branch_id: Optional[uuid.UUID] = None,
    date_from=None,
    date_to=None,
) -> list[tuple[Account, Decimal, Decimal]]:
    """Trial balance grouped by account.

    Returns a list of ``(Account, sum_debit, sum_credit)`` ordered by code.
    Accounts with zero activity are *omitted* (keeps the report scannable).
    Caller computes net balance per row using ``AccountType.is_debit_positive``.
    """
    stmt = (
        select(
            Account,
            func.coalesce(func.sum(JournalLine.debit), 0).label("dr"),
            func.coalesce(func.sum(JournalLine.credit), 0).label("cr"),
        )
        .select_from(Account)
        .join(JournalLine, JournalLine.account_id == Account.id)
        .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
        .where(Account.tenant_id == tenant_id)
        .group_by(Account.id)
        .order_by(Account.code)
    )
    if branch_id is not None:
        stmt = stmt.where(JournalEntry.branch_id == branch_id)
    if date_from is not None:
        stmt = stmt.where(JournalEntry.entry_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(JournalEntry.entry_date <= date_to)

    rows = session.execute(stmt).all()
    return [(r[0], Decimal(r[1]), Decimal(r[2])) for r in rows]
