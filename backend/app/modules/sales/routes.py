"""Sales HTTP routes.

    POST   /api/v1/sales/                      — create (cash | credit | mixed | service)
    GET    /api/v1/sales/                      — list / filter / paginate
    GET    /api/v1/sales/{id}                  — get one
    POST   /api/v1/sales/{id}/payments         — collect debt
    POST   /api/v1/sales/{id}/refund           — refund the whole sale
    GET    /api/v1/sales/debts                 — outstanding credit sales
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
from app.modules.rbac import Permission
from app.modules.sales import service
from app.modules.sales.models import Sale, SaleLine
from app.modules.sales.schemas import PaymentRequest, SaleCreate, SaleLineResponse, SaleResponse


sales_bp = Blueprint("sales", __name__, url_prefix="/sales")


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


def _line_payload(l: SaleLine) -> SaleLineResponse:
    # Lazy-resolve the linked device so the response carries IMEI + warranty.
    device = None
    if l.device_instance_id:
        from app.modules.devices.models import DeviceInstance
        device = db.session.get(DeviceInstance, l.device_instance_id)
    return SaleLineResponse(
        id=l.id,
        product_id=l.product_id,
        description=l.description,
        qty=l.qty,
        unit_price=l.unit_price,
        discount=l.discount,
        line_total=l.line_total,
        cost_snapshot=l.cost_snapshot,
        is_service=l.is_service,
        device_instance_id=l.device_instance_id,
        device_imei=(device.imei if device else None),
        device_serial=(device.serial_number if device else None),
        warranty_ends_at=(device.warranty_ends_at if device else None),
    )


def _sale_payload(s: Sale) -> dict:
    return SaleResponse(
        id=s.id,
        sale_number=s.sale_number,
        branch_id=s.branch_id,
        customer_id=s.customer_id,
        customer_name=s.customer_name,
        sale_date=s.sale_date,
        subtotal=s.subtotal,
        discount_total=s.discount_total,
        total=s.total,
        paid_amount=s.paid_amount,
        is_paid=s.is_paid,
        status=s.status.value,
        notes=s.notes,
        lines=[_line_payload(l) for l in s.lines],
        created_at=s.created_at,
    ).model_dump(mode="json")


def _parse_date(v: str | None) -> date | None:
    if not v:
        return None
    try:
        return date.fromisoformat(v)
    except ValueError:
        raise BadRequest(f"Invalid date '{v}'.")


def _parse_uuid(v: str | None) -> uuid.UUID | None:
    if not v:
        return None
    try:
        return uuid.UUID(v)
    except ValueError:
        raise BadRequest(f"Invalid UUID '{v}'.")


# --- Routes ---------------------------------------------------------------

@sales_bp.post("/")
@require_perm(Permission.SALES_CREATE)
def create_route():
    tenant_id = _tenant_id()
    payload = parse_json(SaleCreate)
    sale = service.create_sale(
        tenant_id=tenant_id,
        payload=payload,
        cashier_id=_user_uuid(),
    )
    db.session.commit()
    return created(_sale_payload(sale))


@sales_bp.get("/")
@require_perm(Permission.SALES_READ)
def list_route():
    tenant_id = _tenant_id()
    pa = parse_page_args()
    page = service.list_sales(
        tenant_id=tenant_id,
        page=pa.page,
        per_page=pa.per_page,
        branch_id=_parse_uuid(request.args.get("branch_id")),
        customer_id=_parse_uuid(request.args.get("customer_id")),
        date_from=_parse_date(request.args.get("from")),
        date_to=_parse_date(request.args.get("to")),
        only_unpaid=(request.args.get("unpaid") == "1"),
    )
    page["items"] = [_sale_payload(s) for s in page["items"]]
    return paged(page)


@sales_bp.get("/debts")
@require_perm(Permission.DEBTS_READ)
def list_debts_route():
    tenant_id = _tenant_id()
    pa = parse_page_args()
    page = service.list_open_debts(
        tenant_id=tenant_id, page=pa.page, per_page=pa.per_page
    )
    page["items"] = [_sale_payload(s) for s in page["items"]]
    return paged(page)


@sales_bp.get("/<uuid:sale_id>")
@require_perm(Permission.SALES_READ)
def get_route(sale_id: uuid.UUID):
    tenant_id = _tenant_id()
    return ok(_sale_payload(service.get_sale(tenant_id=tenant_id, sale_id=sale_id)))


@sales_bp.post("/<uuid:sale_id>/payments")
@require_perm(Permission.DEBTS_COLLECT)
def collect_payment_route(sale_id: uuid.UUID):
    tenant_id = _tenant_id()
    payload = parse_json(PaymentRequest)
    payment = service.apply_payment(
        tenant_id=tenant_id,
        sale_id=sale_id,
        amount=payload.amount,
        payment_date=payload.payment_date,
        method=payload.method,
        notes=payload.notes,
        received_by_id=_user_uuid(),
    )
    db.session.commit()
    sale = service.get_sale(tenant_id=tenant_id, sale_id=sale_id)
    return created({
        "payment_id": str(payment.id),
        "amount": str(payment.amount),
        "sale": _sale_payload(sale),
    })


@sales_bp.post("/<uuid:sale_id>/refund")
@require_perm(Permission.SALES_REFUND)
def refund_route(sale_id: uuid.UUID):
    tenant_id = _tenant_id()
    body = request.get_json(silent=True) or {}
    reason = (body.get("reason") or "").strip()
    if not reason:
        raise BadRequest("reason is required")
    sale = service.refund_sale(
        tenant_id=tenant_id,
        sale_id=sale_id,
        reason=reason,
        user_id=_user_uuid(),
    )
    db.session.commit()
    return ok(_sale_payload(sale))
