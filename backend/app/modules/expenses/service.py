"""Expenses service.

Each expense posts:

    DR <expense_account>   amount
    CR Cash (or BANK)      amount

Account selection: caller may pass an explicit ``expense_account_id`` OR a
``expense_account_key`` (system_key like ``RENT``, ``SALARIES``, ``UTILITIES``,
``OPERATING_EXPENSES``). One of the two is required.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date as date_t
from decimal import Decimal
from typing import Optional

from werkzeug.exceptions import BadRequest, NotFound

from app.core.pagination import paginate_offset
from app.extensions import db
from app.modules.accounting import service as acct
from app.modules.accounting.coa_seed import SystemAccount
from app.modules.accounting.repository import get_account, get_system_account
from app.modules.accounting.service import LineInput
from app.modules.expenses import repository as repo
from app.modules.expenses.models import Expense
from app.modules.expenses.schemas import ExpenseCreate


log = logging.getLogger(__name__)


# --- Create ---------------------------------------------------------------

def create_expense(
    *,
    tenant_id: uuid.UUID,
    payload: ExpenseCreate,
    user_id: Optional[uuid.UUID] = None,
) -> Expense:
    session = db.session

    account_id = _resolve_expense_account(tenant_id, payload)
    expense_date = payload.expense_date or date_t.today()

    expense = Expense(
        tenant_id=tenant_id,
        branch_id=payload.branch_id,
        expense_date=expense_date,
        expense_account_id=account_id,
        amount=payload.amount,
        payment_method=payload.payment_method,
        description=payload.description.strip(),
        reference=payload.reference,
        notes=payload.notes,
        created_by_id=user_id,
    )
    repo.add(session, expense)

    cash_key = SystemAccount.CASH if payload.payment_method == "cash" else SystemAccount.BANK
    entry = acct.post_journal_entry(
        tenant_id=tenant_id,
        entry_date=expense_date,
        branch_id=payload.branch_id,
        source="expense",
        source_ref=f"expense:{expense.id}",
        reference=payload.reference,
        description=payload.description,
        posted_by_id=user_id,
        lines=[
            LineInput(
                account_id=account_id,
                debit=payload.amount,
                description=payload.description,
            ),
            LineInput(
                account_id=acct.get_system_account_id(tenant_id, cash_key),
                credit=payload.amount,
                description=f"Paid via {payload.payment_method}",
            ),
        ],
    )
    expense.journal_entry_id = entry.id
    session.flush()
    log.info(
        "expense_created",
        extra={
            "tenant_id": str(tenant_id),
            "expense_id": str(expense.id),
            "amount": str(payload.amount),
            "account": str(account_id),
        },
    )
    return expense


def _resolve_expense_account(
    tenant_id: uuid.UUID, payload: ExpenseCreate
) -> uuid.UUID:
    session = db.session
    if payload.expense_account_id is not None:
        a = get_account(session, payload.expense_account_id)
        if a is None or a.tenant_id != tenant_id or not a.is_active:
            raise NotFound("Expense account not found.")
        return a.id
    if payload.expense_account_key:
        a = get_system_account(
            session, tenant_id=tenant_id, system_key=payload.expense_account_key
        )
        if a is None:
            raise NotFound(f"Expense account '{payload.expense_account_key}' not found.")
        return a.id
    # Default bucket
    a = get_system_account(
        session, tenant_id=tenant_id, system_key=SystemAccount.OPERATING_EXPENSES
    )
    if a is None:
        raise BadRequest("No expense account configured for this tenant.")
    return a.id


# --- Reads ----------------------------------------------------------------

def get_expense(*, tenant_id: uuid.UUID, expense_id: uuid.UUID) -> Expense:
    e = repo.get(db.session, expense_id)
    if e is None or e.tenant_id != tenant_id or e.deleted_at is not None:
        raise NotFound("Expense not found.")
    return e


def list_expenses(
    *,
    tenant_id: uuid.UUID,
    page: int,
    per_page: int,
    branch_id: Optional[uuid.UUID] = None,
    account_id: Optional[uuid.UUID] = None,
    date_from: Optional[date_t] = None,
    date_to: Optional[date_t] = None,
) -> dict:
    stmt = repo.list_query(
        tenant_id=tenant_id,
        branch_id=branch_id,
        account_id=account_id,
        date_from=date_from,
        date_to=date_to,
    )
    return paginate_offset(db.session, stmt, page=page, per_page=per_page)


# --- Void (reversal) -----------------------------------------------------

def void_expense(
    *,
    tenant_id: uuid.UUID,
    expense_id: uuid.UUID,
    reason: str,
    user_id: Optional[uuid.UUID] = None,
) -> Expense:
    """Reverse the underlying journal entry and soft-delete the expense."""
    from datetime import datetime as dt_t
    session = db.session
    expense = get_expense(tenant_id=tenant_id, expense_id=expense_id)
    if expense.journal_entry_id:
        acct.reverse_journal_entry(
            tenant_id=tenant_id,
            entry_id=expense.journal_entry_id,
            reason=f"Void expense {expense.id}: {reason}",
            posted_by_id=user_id,
        )
    expense.deleted_at = dt_t.utcnow()
    expense.notes = (expense.notes or "") + f"\nVOID: {reason}"
    session.flush()
    return expense
