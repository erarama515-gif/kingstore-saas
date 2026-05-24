"""Customer HTTP routes.

    GET    /api/v1/customers/                       list, paginated, ?q, ?with_debt
    POST   /api/v1/customers/                       create (optional opening_balance)
    GET    /api/v1/customers/lookup?q=...           POS-shaped lookup (top 10)
    GET    /api/v1/customers/<id>                   get one
    PATCH  /api/v1/customers/<id>                   update
    DELETE /api/v1/customers/<id>                   soft delete
    GET    /api/v1/customers/<id>/balance           live AR from ledger
    GET    /api/v1/customers/<id>/statement?from&to AR statement
"""

from __future__ import annotations

import uuid
from datetime import date

from flask import Blueprint, g, request
from flask_jwt_extended import get_jwt_identity
from werkzeug.exceptions import BadRequest

from app.core.http.responses import created, no_content, ok, paged
from app.core.http.validation import parse_json
from app.core.pagination import parse_page_args
from app.core.permissions import require_perm
from app.extensions import db
from app.modules.customers import service
from app.modules.customers.models import Customer
from app.modules.customers.schemas import (
    CustomerBalanceResponse,
    CustomerCreate,
    CustomerQuickHit,
    CustomerResponse,
    CustomerStatementLine,
    CustomerStatementResponse,
    CustomerUpdate,
)
from app.modules.rbac import Permission


customers_bp = Blueprint("customers", __name__, url_prefix="/customers")


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


def _payload(c: Customer) -> dict:
    return CustomerResponse(
        id=c.id,
        name=c.name,
        name_ar=c.name_ar,
        phone=c.phone,
        email=c.email,
        address=c.address,
        notes=c.notes,
        total_spent_cached=c.total_spent_cached,
        debt_cached=c.debt_cached,
        visits_count=c.visits_count,
        last_txn_at=c.last_txn_at,
        is_active=c.is_active,
        created_at=c.created_at,
        updated_at=c.updated_at,
    ).model_dump(mode="json")


def _parse_date(v: str | None) -> date | None:
    if not v:
        return None
    try:
        return date.fromisoformat(v)
    except ValueError:
        raise BadRequest(f"Invalid date '{v}', expected YYYY-MM-DD.")


# --- Routes ----------------------------------------------------------------

@customers_bp.get("/")
@require_perm(Permission.CUSTOMERS_READ)
def list_route():
    tenant_id = _tenant_id()
    pa = parse_page_args()
    page = service.list_customers(
        tenant_id=tenant_id,
        page=pa.page,
        per_page=pa.per_page,
        search=request.args.get("q") or None,
        only_active=(request.args.get("active", "1") == "1"),
        only_with_debt=(request.args.get("with_debt") == "1"),
    )
    page["items"] = [_payload(c) for c in page["items"]]
    return paged(page)


@customers_bp.post("/")
@require_perm(Permission.CUSTOMERS_MANAGE)
def create_route():
    tenant_id = _tenant_id()
    payload = parse_json(CustomerCreate)
    customer = service.create_customer(
        tenant_id=tenant_id, payload=payload, user_id=_user_uuid()
    )
    db.session.commit()
    return created(_payload(customer))


@customers_bp.get("/lookup")
@require_perm(Permission.CUSTOMERS_READ)
def lookup_route():
    tenant_id = _tenant_id()
    q = request.args.get("q", "").strip()
    if not q:
        return ok([])
    matches = service.quick_lookup(tenant_id=tenant_id, query=q, limit=10)
    return ok([
        CustomerQuickHit(
            id=c.id,
            name=c.name,
            name_ar=c.name_ar,
            phone=c.phone,
            debt=c.debt_cached,
        ).model_dump(mode="json")
        for c in matches
    ])


@customers_bp.get("/<uuid:customer_id>")
@require_perm(Permission.CUSTOMERS_READ)
def get_route(customer_id: uuid.UUID):
    tenant_id = _tenant_id()
    return ok(_payload(service.get_customer(tenant_id=tenant_id, customer_id=customer_id)))


@customers_bp.patch("/<uuid:customer_id>")
@require_perm(Permission.CUSTOMERS_MANAGE)
def update_route(customer_id: uuid.UUID):
    tenant_id = _tenant_id()
    payload = parse_json(CustomerUpdate)
    c = service.update_customer(
        tenant_id=tenant_id, customer_id=customer_id, payload=payload
    )
    db.session.commit()
    return ok(_payload(c))


@customers_bp.delete("/<uuid:customer_id>")
@require_perm(Permission.CUSTOMERS_MANAGE)
def delete_route(customer_id: uuid.UUID):
    tenant_id = _tenant_id()
    service.delete_customer(tenant_id=tenant_id, customer_id=customer_id)
    db.session.commit()
    return no_content()


@customers_bp.get("/<uuid:customer_id>/balance")
@require_perm(Permission.CUSTOMERS_READ)
def balance_route(customer_id: uuid.UUID):
    tenant_id = _tenant_id()
    b = service.customer_balance(tenant_id=tenant_id, customer_id=customer_id)
    db.session.commit()  # cache re-sync
    return ok(CustomerBalanceResponse(
        customer_id=b.customer_id,
        debt=b.debt,
        total_spent=b.total_spent,
        visits_count=b.visits_count,
        last_txn_at=b.last_txn_at,
    ).model_dump(mode="json"))


@customers_bp.get("/<uuid:customer_id>/statement")
@require_perm(Permission.CUSTOMERS_READ)
def statement_route(customer_id: uuid.UUID):
    tenant_id = _tenant_id()
    payload = service.customer_statement(
        tenant_id=tenant_id,
        customer_id=customer_id,
        date_from=_parse_date(request.args.get("from")),
        date_to=_parse_date(request.args.get("to")),
    )
    resp = CustomerStatementResponse(
        customer_id=payload["customer_id"],
        customer_name=payload["customer_name"],
        opening_balance=payload["opening_balance"],
        closing_balance=payload["closing_balance"],
        lines=[CustomerStatementLine(**l) for l in payload["lines"]],
    )
    return ok(resp.model_dump(mode="json"))


@customers_bp.get("/<uuid:customer_id>/devices")
@require_perm(Permission.CUSTOMERS_READ)
def customer_devices_route(customer_id: uuid.UUID):
    """List all devices owned by this customer (status=sold or under_repair)."""
    tid = _tenant_id()
    # Verify the customer belongs to this tenant first
    cust = repo.get_by_id(db.session, customer_id)
    if cust is None or cust.tenant_id != tid:
        from werkzeug.exceptions import NotFound
        raise NotFound("Customer not found.")
    from app.modules.devices import service as device_service
    devices = device_service.list_for_customer(tenant_id=tid, customer_id=customer_id)
    return ok([
        {
            "id": str(d.id),
            "product_id": str(d.product_id),
            "product_name": getattr(d.product, "name", None),
            "imei": d.imei,
            "serial_number": d.serial_number,
            "status": d.status.value,
            "sold_at": d.sold_at.isoformat() if d.sold_at else None,
            "warranty_ends_at": d.warranty_ends_at.isoformat() if d.warranty_ends_at else None,
            "is_under_warranty": d.is_under_warranty,
        }
        for d in devices
    ])
