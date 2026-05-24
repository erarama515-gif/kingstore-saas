"""Capital HTTP routes.

    GET    /api/v1/capital/summary       — KPIs: cash, inventory, equity
    GET    /api/v1/capital/movements     — paginated history (source=capital)
    POST   /api/v1/capital/inject        — DR Cash / CR Owner's Capital
    POST   /api/v1/capital/withdraw      — DR Owner's Drawings / CR Cash
"""

from __future__ import annotations

import uuid

from flask import Blueprint, g
from flask_jwt_extended import get_jwt_identity
from werkzeug.exceptions import BadRequest

from app.core.http.responses import created, ok, paged
from app.core.http.validation import parse_json
from app.core.pagination import parse_page_args
from app.core.permissions import require_perm
from app.extensions import db
from app.modules.capital import service
from app.modules.capital.schemas import CapitalMovementRequest
from app.modules.rbac import Permission


capital_bp = Blueprint("capital", __name__, url_prefix="/capital")


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


@capital_bp.get("/summary")
@require_perm(Permission.CAPITAL_READ)
def summary_route():
    s = service.capital_summary(tenant_id=_tenant_id())
    return ok({
        "liquid_cash": str(s.liquid_cash),
        "inventory_value": str(s.inventory_value),
        "total_working_capital": str(s.total_working_capital),
        "owner_capital": str(s.owner_capital),
        "owner_drawings": str(s.owner_drawings),
        "retained_earnings": str(s.retained_earnings),
        "net_owner_equity": str(s.net_owner_equity),
    })


@capital_bp.get("/movements")
@require_perm(Permission.CAPITAL_READ)
def movements_route():
    pa = parse_page_args()
    page = service.list_capital_movements(
        tenant_id=_tenant_id(), page=pa.page, per_page=pa.per_page
    )
    page["items"] = [
        {
            "id": str(e.id),
            "entry_date": e.entry_date.isoformat(),
            "reference": e.reference,
            "description": e.description,
            "posted_at": e.posted_at.isoformat() if e.posted_at else None,
            "lines": [
                {
                    "account_id": str(l.account_id),
                    "debit": str(l.debit),
                    "credit": str(l.credit),
                    "description": l.description,
                }
                for l in e.lines
            ],
        }
        for e in page["items"]
    ]
    return paged(page)


@capital_bp.post("/inject")
@require_perm(Permission.CAPITAL_MANAGE)
def inject_route():
    tenant_id = _tenant_id()
    payload = parse_json(CapitalMovementRequest)
    entry = service.capital_inject(
        tenant_id=tenant_id,
        amount=payload.amount,
        description=payload.description,
        branch_id=payload.branch_id,
        movement_date=payload.movement_date,
        user_id=_user_uuid(),
    )
    db.session.commit()
    return created({"journal_entry_id": str(entry.id), "amount": str(payload.amount)})


@capital_bp.post("/withdraw")
@require_perm(Permission.CAPITAL_MANAGE)
def withdraw_route():
    tenant_id = _tenant_id()
    payload = parse_json(CapitalMovementRequest)
    entry = service.capital_withdraw(
        tenant_id=tenant_id,
        amount=payload.amount,
        description=payload.description,
        branch_id=payload.branch_id,
        movement_date=payload.movement_date,
        user_id=_user_uuid(),
    )
    db.session.commit()
    return created({"journal_entry_id": str(entry.id), "amount": str(payload.amount)})
