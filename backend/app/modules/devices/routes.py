"""Devices HTTP routes.

    GET   /api/v1/devices/                       — paginated list w/ filters
    POST  /api/v1/devices/                       — register a new device
    GET   /api/v1/devices/lookup?q=IMEI          — single device + history
    GET   /api/v1/devices/<id>                   — device detail
    GET   /api/v1/customers/<id>/devices         — see customers routes
"""

from __future__ import annotations

import uuid

from flask import Blueprint, g, request
from sqlalchemy import select
from werkzeug.exceptions import BadRequest, NotFound

from app.core.http.responses import created, ok, paged
from app.core.http.validation import parse_json
from app.core.pagination import paginate_offset, parse_page_args
from app.core.permissions import require_perm
from app.extensions import db
from app.modules.devices import repository as repo
from app.modules.devices import service
from app.modules.devices.models import DeviceInstance, DeviceStatus
from app.modules.devices.schemas import DeviceRegister, DeviceResponse
from app.modules.rbac import Permission


devices_bp = Blueprint("devices", __name__, url_prefix="/devices")


def _tid() -> uuid.UUID:
    tid = getattr(g, "tenant_id", None)
    if tid is None:
        raise BadRequest("Tenant context required.")
    return tid


def _parse_uuid(v: str | None) -> uuid.UUID | None:
    if not v:
        return None
    try:
        return uuid.UUID(v)
    except ValueError:
        raise BadRequest(f"Invalid UUID '{v}'.")


def _payload(d: DeviceInstance) -> dict:
    return DeviceResponse(
        id=d.id,
        product_id=d.product_id,
        product_name=getattr(d.product, "name", None),
        branch_id=d.branch_id,
        imei=d.imei,
        serial_number=d.serial_number,
        status=d.status.value,
        customer_id=d.customer_id,
        sale_id=d.sale_id,
        sold_at=d.sold_at,
        warranty_ends_at=d.warranty_ends_at,
        is_under_warranty=d.is_under_warranty,
        purchase_cost=d.purchase_cost,
        notes=d.notes,
        created_at=d.created_at,
        updated_at=d.updated_at,
    ).model_dump(mode="json")


# --- Routes -----------------------------------------------------------------

@devices_bp.get("/")
@require_perm(Permission.PRODUCTS_READ)
def list_route():
    tid = _tid()
    pa = parse_page_args()
    raw_status = request.args.get("status")
    status = DeviceStatus(raw_status) if raw_status else None
    stmt = repo.search_query(
        tenant_id=tid,
        q=request.args.get("q"),
        status=status,
        branch_id=_parse_uuid(request.args.get("branch_id")),
        customer_id=_parse_uuid(request.args.get("customer_id")),
        product_id=_parse_uuid(request.args.get("product_id")),
    )
    page = paginate_offset(db.session, stmt, pa.page, pa.per_page)
    page["items"] = [_payload(d) for d in page["items"]]
    return paged(page)


@devices_bp.post("/")
@require_perm(Permission.PRODUCTS_UPDATE)
def register_route():
    tid = _tid()
    payload = parse_json(DeviceRegister)
    device = service.register_device(
        tenant_id=tid,
        product_id=payload.product_id,
        branch_id=payload.branch_id,
        imei=payload.imei,
        serial_number=payload.serial_number,
        purchase_cost=payload.purchase_cost,
        notes=payload.notes,
    )
    db.session.commit()
    return created(_payload(device))


@devices_bp.get("/lookup")
@require_perm(Permission.PRODUCTS_READ)
def lookup_route():
    """Rich lookup: device + last repairs + originating sale summary."""
    tid = _tid()
    q = (request.args.get("q") or "").strip()
    if not q:
        raise BadRequest("Query parameter q (IMEI or serial) required.")
    device = service.lookup_by_identifier(tenant_id=tid, identifier=q)
    if device is None:
        raise NotFound("No device with that identifier.")

    # Recent repairs for this specific device
    from app.modules.repairs.models import RepairTicket
    repairs = db.session.execute(
        select(RepairTicket)
        .where(
            RepairTicket.tenant_id == tid,
            RepairTicket.device_instance_id == device.id,
            RepairTicket.deleted_at.is_(None),
        )
        .order_by(RepairTicket.date_in.desc())
        .limit(20)
    ).scalars().all()

    # Originating sale summary (if linked)
    sale_summary = None
    if device.sale_id:
        from app.modules.sales.models import Sale
        sale = db.session.get(Sale, device.sale_id)
        if sale is not None and sale.tenant_id == tid:
            sale_summary = {
                "id": str(sale.id),
                "sale_number": sale.sale_number,
                "sale_date": sale.sale_date.isoformat(),
                "total": str(sale.total),
                "customer_name": sale.customer_name,
            }

    return ok({
        "device": _payload(device),
        "recent_repairs": [
            {
                "id": str(r.id),
                "ticket_number": r.ticket_number,
                "status": r.status.value,
                "date_in": r.date_in.isoformat(),
                "problem": r.problem,
                "actual_cost": str(r.actual_cost),
            }
            for r in repairs
        ],
        "sale": sale_summary,
    })


@devices_bp.get("/<uuid:device_id>")
@require_perm(Permission.PRODUCTS_READ)
def get_route(device_id: uuid.UUID):
    tid = _tid()
    d = repo.get_by_id(db.session, device_id)
    if d is None or d.tenant_id != tid or d.deleted_at is not None:
        raise NotFound("Device not found.")
    return ok(_payload(d))
