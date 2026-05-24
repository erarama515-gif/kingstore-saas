"""Expenses HTTP routes.

    GET    /api/v1/expenses/         — list (paginated, filters)
    POST   /api/v1/expenses/         — create + post journal
    GET    /api/v1/expenses/{id}
    DELETE /api/v1/expenses/{id}     — void (reverse journal + soft-delete)
"""

from __future__ import annotations

import uuid
from datetime import date

from flask import Blueprint, g, request
from flask_jwt_extended import get_jwt_identity
from werkzeug.exceptions import BadRequest

from app.core.http.responses import created, ok, paged
from app.core.http.validation import parse_json
from app.core.pagination import parse_page_args
from app.core.permissions import require_perm
from app.extensions import db
from app.modules.expenses import service
from app.modules.expenses.models import Expense
from app.modules.expenses.schemas import ExpenseCreate, ExpenseResponse
from app.modules.rbac import Permission


expenses_bp = Blueprint("expenses", __name__, url_prefix="/expenses")


def _tenant_id() -> uuid.UUID:
    tid = getattr(g, "tenant_id", None)
    if tid is None:
        raise BadRequest("Tenant context required.")
    return tid


def _user_uuid() -> uuid.UUID | None:
    ident = get_jwt_identity()
    if not ident:
        return None
    try:
        return uuid.UUID(ident)
    except ValueError:
        return None


def _payload(e: Expense) -> dict:
    return ExpenseResponse(
        id=e.id,
        branch_id=e.branch_id,
        expense_date=e.expense_date,
        expense_account_id=e.expense_account_id,
        amount=e.amount,
        payment_method=e.payment_method,
        description=e.description,
        reference=e.reference,
        notes=e.notes,
        journal_entry_id=e.journal_entry_id,
        created_at=e.created_at,
    ).model_dump(mode="json")


def _parse_uuid(v):
    if not v:
        return None
    try:
        return uuid.UUID(v)
    except ValueError:
        raise BadRequest(f"Invalid UUID '{v}'.")


def _parse_date(v):
    if not v:
        return None
    try:
        return date.fromisoformat(v)
    except ValueError:
        raise BadRequest(f"Invalid date '{v}'.")


@expenses_bp.get("/")
@require_perm(Permission.EXPENSES_READ)
def list_route():
    tenant_id = _tenant_id()
    pa = parse_page_args()
    page = service.list_expenses(
        tenant_id=tenant_id,
        page=pa.page,
        per_page=pa.per_page,
        branch_id=_parse_uuid(request.args.get("branch_id")),
        account_id=_parse_uuid(request.args.get("account_id")),
        date_from=_parse_date(request.args.get("from")),
        date_to=_parse_date(request.args.get("to")),
    )
    page["items"] = [_payload(e) for e in page["items"]]
    return paged(page)


@expenses_bp.post("/")
@require_perm(Permission.EXPENSES_CREATE)
def create_route():
    tenant_id = _tenant_id()
    payload = parse_json(ExpenseCreate)
    expense = service.create_expense(
        tenant_id=tenant_id, payload=payload, user_id=_user_uuid()
    )
    db.session.commit()
    return created(_payload(expense))


@expenses_bp.get("/<uuid:expense_id>")
@require_perm(Permission.EXPENSES_READ)
def get_route(expense_id: uuid.UUID):
    tenant_id = _tenant_id()
    return ok(_payload(service.get_expense(tenant_id=tenant_id, expense_id=expense_id)))


@expenses_bp.delete("/<uuid:expense_id>")
@require_perm(Permission.EXPENSES_CREATE)
def void_route(expense_id: uuid.UUID):
    tenant_id = _tenant_id()
    body = request.get_json(silent=True) or {}
    reason = (body.get("reason") or "User-requested void").strip()
    expense = service.void_expense(
        tenant_id=tenant_id, expense_id=expense_id, reason=reason, user_id=_user_uuid()
    )
    db.session.commit()
    return ok(_payload(expense))
