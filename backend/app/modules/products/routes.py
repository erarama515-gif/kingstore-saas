"""Products HTTP routes.

Endpoints under ``/api/v1/products``:

    GET    /                       — list/search/filter, paginated
    POST   /                       — create
    GET    /lookup?q=...           — single POS lookup (code → barcode → name)
    GET    /<id>                   — get one
    PATCH  /<id>                   — update fields
    DELETE /<id>                   — soft delete
"""

from __future__ import annotations

import uuid

from flask import Blueprint, request

from app.core.http.responses import created, no_content, ok, paged
from app.core.http.validation import parse_json
from app.core.pagination import parse_page_args
from app.core.permissions import require_perm
from app.extensions import db
from app.modules.products import service
from app.modules.products.models import Product, ProductCategory
from app.modules.products.schemas import ProductCreate, ProductResponse, ProductUpdate
from app.modules.rbac import Permission


products_bp = Blueprint("products", __name__, url_prefix="/products")


def _payload(p: Product) -> dict:
    return ProductResponse(
        id=p.id,
        name=p.name,
        name_ar=p.name_ar,
        category=p.category.value,
        code=p.code,
        barcode=p.barcode,
        cost=p.cost,
        price=p.price,
        reorder_point=p.reorder_point,
        is_active=p.is_active,
        description=p.description,
        created_at=p.created_at,
        updated_at=p.updated_at,
    ).model_dump(mode="json")


def _current_tenant() -> uuid.UUID:
    from flask import g
    from werkzeug.exceptions import BadRequest
    tid = getattr(g, "tenant_id", None)
    if tid is None:
        raise BadRequest("Tenant context required.")
    return tid


# --- Routes ----------------------------------------------------------------

@products_bp.get("/")
@require_perm(Permission.PRODUCTS_READ)
def list_route():
    tenant_id = _current_tenant()
    pa = parse_page_args()
    raw_cat = request.args.get("category")
    category = ProductCategory(raw_cat) if raw_cat else None
    page = service.list_products(
        tenant_id=tenant_id,
        page=pa.page,
        per_page=pa.per_page,
        category=category,
        search=request.args.get("q") or None,
        only_active=(request.args.get("active", "1") == "1"),
    )
    page["items"] = [_payload(p) for p in page["items"]]
    return paged(page)


@products_bp.post("/")
@require_perm(Permission.PRODUCTS_CREATE)
def create_route():
    tenant_id = _current_tenant()
    payload = parse_json(ProductCreate)
    product = service.create_product(tenant_id=tenant_id, payload=payload)
    db.session.commit()
    return created(_payload(product))


@products_bp.get("/lookup")
@require_perm(Permission.PRODUCTS_READ)
def lookup_route():
    tenant_id = _current_tenant()
    q = request.args.get("q", "").strip()
    product = service.lookup_for_pos(tenant_id=tenant_id, query=q)
    if product is None:
        from werkzeug.exceptions import NotFound
        raise NotFound("No product matches that identifier.")
    return ok(_payload(product))


@products_bp.get("/<uuid:product_id>")
@require_perm(Permission.PRODUCTS_READ)
def get_route(product_id: uuid.UUID):
    tenant_id = _current_tenant()
    return ok(_payload(service.get_product(tenant_id=tenant_id, product_id=product_id)))


@products_bp.patch("/<uuid:product_id>")
@require_perm(Permission.PRODUCTS_UPDATE)
def update_route(product_id: uuid.UUID):
    tenant_id = _current_tenant()
    payload = parse_json(ProductUpdate)
    product = service.update_product(
        tenant_id=tenant_id, product_id=product_id, payload=payload
    )
    db.session.commit()
    return ok(_payload(product))


@products_bp.delete("/<uuid:product_id>")
@require_perm(Permission.PRODUCTS_DELETE)
def delete_route(product_id: uuid.UUID):
    tenant_id = _current_tenant()
    service.delete_product(tenant_id=tenant_id, product_id=product_id)
    db.session.commit()
    return no_content()
