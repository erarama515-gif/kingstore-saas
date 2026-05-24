"""Supplier HTTP routes — symmetric to customers."""

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
from app.modules.rbac import Permission
from app.modules.suppliers import service
from app.modules.suppliers.models import Supplier
from app.modules.suppliers.schemas import (
    SupplierBalanceResponse,
    SupplierCreate,
    SupplierQuickHit,
    SupplierResponse,
    SupplierStatementLine,
    SupplierStatementResponse,
    SupplierUpdate,
)


suppliers_bp = Blueprint("suppliers", __name__, url_prefix="/suppliers")


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


def _payload(s: Supplier) -> dict:
    return SupplierResponse(
        id=s.id,
        name=s.name,
        name_ar=s.name_ar,
        phone=s.phone,
        email=s.email,
        contact_person=s.contact_person,
        address=s.address,
        notes=s.notes,
        total_purchased_cached=s.total_purchased_cached,
        payable_cached=s.payable_cached,
        last_txn_at=s.last_txn_at,
        is_active=s.is_active,
        created_at=s.created_at,
        updated_at=s.updated_at,
    ).model_dump(mode="json")


def _parse_date(v: str | None) -> date | None:
    if not v:
        return None
    try:
        return date.fromisoformat(v)
    except ValueError:
        raise BadRequest(f"Invalid date '{v}', expected YYYY-MM-DD.")


# --- Routes ----------------------------------------------------------------

@suppliers_bp.get("/")
@require_perm(Permission.SUPPLIERS_READ)
def list_route():
    tenant_id = _tenant_id()
    pa = parse_page_args()
    page = service.list_suppliers(
        tenant_id=tenant_id,
        page=pa.page,
        per_page=pa.per_page,
        search=request.args.get("q") or None,
        only_active=(request.args.get("active", "1") == "1"),
        only_with_payable=(request.args.get("with_payable") == "1"),
    )
    page["items"] = [_payload(s) for s in page["items"]]
    return paged(page)


@suppliers_bp.post("/")
@require_perm(Permission.SUPPLIERS_MANAGE)
def create_route():
    tenant_id = _tenant_id()
    payload = parse_json(SupplierCreate)
    supplier = service.create_supplier(
        tenant_id=tenant_id, payload=payload, user_id=_user_uuid()
    )
    db.session.commit()
    return created(_payload(supplier))


@suppliers_bp.get("/lookup")
@require_perm(Permission.SUPPLIERS_READ)
def lookup_route():
    tenant_id = _tenant_id()
    q = request.args.get("q", "").strip()
    if not q:
        return ok([])
    matches = service.quick_lookup(tenant_id=tenant_id, query=q, limit=10)
    return ok([
        SupplierQuickHit(
            id=s.id,
            name=s.name,
            name_ar=s.name_ar,
            phone=s.phone,
            payable=s.payable_cached,
        ).model_dump(mode="json")
        for s in matches
    ])


@suppliers_bp.get("/<uuid:supplier_id>")
@require_perm(Permission.SUPPLIERS_READ)
def get_route(supplier_id: uuid.UUID):
    tenant_id = _tenant_id()
    return ok(_payload(service.get_supplier(tenant_id=tenant_id, supplier_id=supplier_id)))


@suppliers_bp.patch("/<uuid:supplier_id>")
@require_perm(Permission.SUPPLIERS_MANAGE)
def update_route(supplier_id: uuid.UUID):
    tenant_id = _tenant_id()
    payload = parse_json(SupplierUpdate)
    s = service.update_supplier(
        tenant_id=tenant_id, supplier_id=supplier_id, payload=payload
    )
    db.session.commit()
    return ok(_payload(s))


@suppliers_bp.delete("/<uuid:supplier_id>")
@require_perm(Permission.SUPPLIERS_MANAGE)
def delete_route(supplier_id: uuid.UUID):
    tenant_id = _tenant_id()
    service.delete_supplier(tenant_id=tenant_id, supplier_id=supplier_id)
    db.session.commit()
    return no_content()


@suppliers_bp.get("/<uuid:supplier_id>/balance")
@require_perm(Permission.SUPPLIERS_READ)
def balance_route(supplier_id: uuid.UUID):
    tenant_id = _tenant_id()
    b = service.supplier_balance(tenant_id=tenant_id, supplier_id=supplier_id)
    db.session.commit()  # cache re-sync
    return ok(SupplierBalanceResponse(
        supplier_id=b.supplier_id,
        payable=b.payable,
        total_purchased=b.total_purchased,
        last_txn_at=b.last_txn_at,
    ).model_dump(mode="json"))


@suppliers_bp.get("/<uuid:supplier_id>/statement")
@require_perm(Permission.SUPPLIERS_READ)
def statement_route(supplier_id: uuid.UUID):
    tenant_id = _tenant_id()
    payload = service.supplier_statement(
        tenant_id=tenant_id,
        supplier_id=supplier_id,
        date_from=_parse_date(request.args.get("from")),
        date_to=_parse_date(request.args.get("to")),
    )
    resp = SupplierStatementResponse(
        supplier_id=payload["supplier_id"],
        supplier_name=payload["supplier_name"],
        opening_balance=payload["opening_balance"],
        closing_balance=payload["closing_balance"],
        lines=[SupplierStatementLine(**l) for l in payload["lines"]],
    )
    return ok(resp.model_dump(mode="json"))
