"""Repairs HTTP routes.

    GET    /api/v1/repairs/                    — list (status/branch/customer filters)
    POST   /api/v1/repairs/                    — create new ticket
    GET    /api/v1/repairs/{id}
    PATCH  /api/v1/repairs/{id}/status         — workflow transition (no revenue)
    POST   /api/v1/repairs/{id}/deliver        — finalize + post Service Revenue
"""

from __future__ import annotations

import uuid

from flask import Blueprint, g, request
from flask_jwt_extended import get_jwt_identity
from werkzeug.exceptions import BadRequest

from app.core.http.responses import created, ok, paged
from app.core.http.validation import parse_json
from app.core.pagination import parse_page_args
from app.core.permissions import require_perm
from app.extensions import db
from app.modules.rbac import Permission
from app.modules.repairs import service
from app.modules.repairs.models import RepairTicket
from app.modules.repairs.schemas import (
    RepairCreate,
    RepairDeliverRequest,
    RepairResponse,
    RepairStatusUpdate,
)


repairs_bp = Blueprint("repairs", __name__, url_prefix="/repairs")


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


def _parse_uuid(v):
    if not v:
        return None
    try:
        return uuid.UUID(v)
    except ValueError:
        raise BadRequest(f"Invalid UUID '{v}'.")


def _payload(t: RepairTicket) -> dict:
    return RepairResponse(
        id=t.id,
        ticket_number=t.ticket_number,
        branch_id=t.branch_id,
        customer_id=t.customer_id,
        customer_name=t.customer_name,
        customer_phone=t.customer_phone,
        device_model=t.device_model,
        imei=t.imei,
        problem=t.problem,
        estimated_cost=t.estimated_cost,
        actual_cost=t.actual_cost,
        status=t.status.value,
        date_in=t.date_in,
        date_delivered=t.date_delivered,
        is_paid_on_delivery=t.is_paid_on_delivery,
        notes=t.notes,
        delivery_journal_entry_id=t.delivery_journal_entry_id,
        created_at=t.created_at,
    ).model_dump(mode="json")


@repairs_bp.get("/")
@require_perm(Permission.REPAIRS_READ)
def list_route():
    tenant_id = _tenant_id()
    pa = parse_page_args()
    page = service.list_tickets(
        tenant_id=tenant_id,
        page=pa.page,
        per_page=pa.per_page,
        branch_id=_parse_uuid(request.args.get("branch_id")),
        status=request.args.get("status") or None,
        customer_id=_parse_uuid(request.args.get("customer_id")),
    )
    page["items"] = [_payload(t) for t in page["items"]]
    return paged(page)


@repairs_bp.post("/")
@require_perm(Permission.REPAIRS_CREATE)
def create_route():
    tenant_id = _tenant_id()
    payload = parse_json(RepairCreate)
    ticket = service.create_ticket(
        tenant_id=tenant_id, payload=payload, technician_id=_user_uuid()
    )
    db.session.commit()
    return created(_payload(ticket))


@repairs_bp.get("/<uuid:ticket_id>")
@require_perm(Permission.REPAIRS_READ)
def get_route(ticket_id: uuid.UUID):
    tenant_id = _tenant_id()
    return ok(_payload(service.get_ticket(tenant_id=tenant_id, ticket_id=ticket_id)))


@repairs_bp.patch("/<uuid:ticket_id>/status")
@require_perm(Permission.REPAIRS_UPDATE)
def update_status_route(ticket_id: uuid.UUID):
    tenant_id = _tenant_id()
    payload = parse_json(RepairStatusUpdate)
    ticket = service.update_status(
        tenant_id=tenant_id,
        ticket_id=ticket_id,
        new_status=payload.status,
        notes=payload.notes,
    )
    db.session.commit()
    return ok(_payload(ticket))


@repairs_bp.post("/<uuid:ticket_id>/deliver")
@require_perm(Permission.REPAIRS_DELIVER)
def deliver_route(ticket_id: uuid.UUID):
    tenant_id = _tenant_id()
    payload = parse_json(RepairDeliverRequest)
    ticket = service.deliver(
        tenant_id=tenant_id,
        ticket_id=ticket_id,
        payload=payload,
        user_id=_user_uuid(),
    )
    db.session.commit()
    return ok(_payload(ticket))
