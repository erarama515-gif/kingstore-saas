"""Inventory HTTP routes.

    GET   /api/v1/inventory/stock-levels?branch_id&low=1   — list (paginated)
    GET   /api/v1/inventory/stock-levels/<product>/<branch> — one row
    GET   /api/v1/inventory/products/<id>/movements        — product history
    POST  /api/v1/inventory/adjust                         — manual adjustment
"""

from __future__ import annotations

import uuid
from datetime import date

from flask import Blueprint, g, request
from flask_jwt_extended import get_jwt_identity
from werkzeug.exceptions import BadRequest, NotFound

from app.core.http.responses import created, ok, paged
from app.core.http.validation import parse_json
from app.core.pagination import parse_page_args
from app.core.permissions import require_perm
from app.extensions import db
from app.modules.inventory import service
from app.modules.inventory.models import StockLevel, StockMovement
from app.modules.inventory.schemas import (
    StockAdjustmentRequest,
    StockLevelResponse,
    StockMovementResponse,
)
from app.modules.rbac import Permission


inventory_bp = Blueprint("inventory", __name__, url_prefix="/inventory")


def _tenant_id() -> uuid.UUID:
    tid = getattr(g, "tenant_id", None)
    if tid is None:
        raise BadRequest("Tenant context required.")
    return tid


def _level_payload(l: StockLevel) -> dict:
    return StockLevelResponse(
        id=l.id,
        product_id=l.product_id,
        branch_id=l.branch_id,
        qty_on_hand=l.qty_on_hand,
        avg_cost=l.avg_cost,
        updated_at=l.updated_at,
    ).model_dump(mode="json")


def _movement_payload(m: StockMovement) -> dict:
    return StockMovementResponse(
        id=m.id,
        product_id=m.product_id,
        branch_id=m.branch_id,
        movement_type=m.movement_type.value,
        qty=m.qty,
        unit_cost=m.unit_cost,
        movement_date=m.movement_date,
        reference=m.reference,
        notes=m.notes,
        journal_entry_id=m.journal_entry_id,
        created_by_id=m.created_by_id,
    ).model_dump(mode="json")


def _parse_uuid(v: str | None) -> uuid.UUID | None:
    if not v:
        return None
    try:
        return uuid.UUID(v)
    except ValueError:
        raise BadRequest(f"Invalid UUID '{v}'.")


def _parse_date(v: str | None) -> date | None:
    if not v:
        return None
    try:
        return date.fromisoformat(v)
    except ValueError:
        raise BadRequest(f"Invalid date '{v}', expected YYYY-MM-DD.")


def _user_uuid() -> uuid.UUID | None:
    ident = get_jwt_identity()
    if not ident:
        return None
    try:
        return uuid.UUID(ident)
    except ValueError:
        return None


# --- Routes ----------------------------------------------------------------

@inventory_bp.get("/stock-levels")
@require_perm(Permission.INVENTORY_READ)
def list_levels_route():
    tenant_id = _tenant_id()
    branch_id = _parse_uuid(request.args.get("branch_id"))
    if branch_id is None:
        raise BadRequest("branch_id query parameter is required.")
    pa = parse_page_args()
    page = service.list_levels_for_branch(
        tenant_id=tenant_id,
        branch_id=branch_id,
        page=pa.page,
        per_page=pa.per_page,
        only_low_stock=(request.args.get("low") == "1"),
    )
    page["items"] = [_level_payload(l) for l in page["items"]]
    return paged(page)


@inventory_bp.get("/stock-levels/<uuid:product_id>/<uuid:branch_id>")
@require_perm(Permission.INVENTORY_READ)
def get_level_route(product_id: uuid.UUID, branch_id: uuid.UUID):
    tenant_id = _tenant_id()
    level = service.get_stock_level(
        tenant_id=tenant_id, product_id=product_id, branch_id=branch_id
    )
    if level is None:
        # Materialize a zero-qty row in the response without persisting.
        return ok({
            "id": None,
            "product_id": str(product_id),
            "branch_id": str(branch_id),
            "qty_on_hand": 0,
            "avg_cost": "0.0000",
            "updated_at": None,
        })
    return ok(_level_payload(level))


@inventory_bp.get("/products/<uuid:product_id>/movements")
@require_perm(Permission.INVENTORY_READ)
def list_movements_route(product_id: uuid.UUID):
    tenant_id = _tenant_id()
    pa = parse_page_args()
    page = service.list_movements_for_product(
        tenant_id=tenant_id,
        product_id=product_id,
        branch_id=_parse_uuid(request.args.get("branch_id")),
        date_from=_parse_date(request.args.get("from")),
        date_to=_parse_date(request.args.get("to")),
        page=pa.page,
        per_page=pa.per_page,
    )
    page["items"] = [_movement_payload(m) for m in page["items"]]
    return paged(page)


@inventory_bp.post("/adjust")
@require_perm(Permission.INVENTORY_ADJUST)
def adjust_route():
    tenant_id = _tenant_id()
    payload = parse_json(StockAdjustmentRequest)
    result = service.adjust_stock(
        tenant_id=tenant_id,
        product_id=payload.product_id,
        branch_id=payload.branch_id,
        qty=payload.qty,
        direction=payload.direction,
        unit_cost=payload.unit_cost,
        reason=payload.reason,
        movement_date=payload.movement_date,
        user_id=_user_uuid(),
    )
    db.session.commit()
    return created({
        "movement": _movement_payload(result.movement),
        "new_qty": result.new_qty,
        "journal_entry_id": str(result.journal_entry_id) if result.journal_entry_id else None,
    })
