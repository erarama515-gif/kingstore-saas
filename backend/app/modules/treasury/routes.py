"""Treasury HTTP routes.

    GET   /api/v1/treasury/cash-position?branch_id&date=YYYY-MM-DD
    POST  /api/v1/treasury/close-day
    GET   /api/v1/treasury/day-closes?branch_id
    GET   /api/v1/treasury/day-closes/<branch>/<date>
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
from app.modules.rbac import Permission
from app.modules.treasury import service
from app.modules.treasury.models import DayClose
from app.modules.treasury.schemas import CashPositionResponse, CloseDayRequest, DayCloseResponse


treasury_bp = Blueprint("treasury", __name__, url_prefix="/treasury")


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


def _parse_date(v):
    if not v:
        return None
    try:
        return date.fromisoformat(v)
    except ValueError:
        raise BadRequest(f"Invalid date '{v}'.")


def _parse_uuid(v):
    if not v:
        return None
    try:
        return uuid.UUID(v)
    except ValueError:
        raise BadRequest(f"Invalid UUID '{v}'.")


def _close_payload(c: DayClose) -> dict:
    return DayCloseResponse(
        id=c.id,
        branch_id=c.branch_id,
        business_date=c.business_date,
        opening_cash=c.opening_cash,
        cash_in=c.cash_in,
        cash_out=c.cash_out,
        expected_cash=c.expected_cash,
        counted_cash=c.counted_cash,
        variance=c.variance,
        notes=c.notes,
        closed_at=c.closed_at,
    ).model_dump(mode="json")


@treasury_bp.get("/cash-position")
@require_perm(Permission.TREASURY_READ)
def cash_position_route():
    tenant_id = _tenant_id()
    pos = service.cash_position(
        tenant_id=tenant_id,
        branch_id=_parse_uuid(request.args.get("branch_id")),
        business_date=_parse_date(request.args.get("date")),
    )
    return ok(CashPositionResponse(
        cash_balance=pos.cash_balance,
        bank_balance=pos.bank_balance,
        today_cash_in=pos.today_cash_in,
        today_cash_out=pos.today_cash_out,
        today_net=pos.today_net,
        business_date=pos.business_date,
    ).model_dump(mode="json"))


@treasury_bp.post("/close-day")
@require_perm(Permission.TREASURY_CLOSE_DAY)
def close_day_route():
    tenant_id = _tenant_id()
    payload = parse_json(CloseDayRequest)
    close = service.close_day(
        tenant_id=tenant_id,
        branch_id=payload.branch_id,
        counted_cash=payload.counted_cash,
        business_date=payload.business_date,
        notes=payload.notes,
        closed_by_id=_user_uuid(),
    )
    db.session.commit()
    return created(_close_payload(close))


@treasury_bp.get("/day-closes")
@require_perm(Permission.TREASURY_READ)
def list_day_closes_route():
    tenant_id = _tenant_id()
    pa = parse_page_args()
    page = service.list_day_closes(
        tenant_id=tenant_id,
        branch_id=_parse_uuid(request.args.get("branch_id")),
        page=pa.page,
        per_page=pa.per_page,
    )
    page["items"] = [_close_payload(c) for c in page["items"]]
    return paged(page)


@treasury_bp.get("/day-closes/<uuid:branch_id>/<string:business_date>")
@require_perm(Permission.TREASURY_READ)
def get_day_close_route(branch_id: uuid.UUID, business_date: str):
    tenant_id = _tenant_id()
    bd = _parse_date(business_date)
    if bd is None:
        raise BadRequest("Invalid date.")
    close = service.day_snapshot(tenant_id=tenant_id, branch_id=branch_id, business_date=bd)
    if close is None:
        raise NotFound("No close for that branch/date.")
    return ok(_close_payload(close))
