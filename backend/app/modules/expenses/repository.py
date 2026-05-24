"""Expenses data access."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Optional

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.modules.expenses.models import Expense


def get(session: Session, expense_id: uuid.UUID) -> Optional[Expense]:
    return session.get(Expense, expense_id)


def add(session: Session, expense: Expense) -> Expense:
    session.add(expense)
    session.flush()
    return expense


def list_query(
    *,
    tenant_id: uuid.UUID,
    branch_id: Optional[uuid.UUID] = None,
    account_id: Optional[uuid.UUID] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> Select:
    stmt = (
        select(Expense)
        .where(Expense.tenant_id == tenant_id, Expense.deleted_at.is_(None))
        .order_by(Expense.expense_date.desc(), Expense.created_at.desc())
    )
    if branch_id is not None:
        stmt = stmt.where(Expense.branch_id == branch_id)
    if account_id is not None:
        stmt = stmt.where(Expense.expense_account_id == account_id)
    if date_from is not None:
        stmt = stmt.where(Expense.expense_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(Expense.expense_date <= date_to)
    return stmt
