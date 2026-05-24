"""Products service.

Public surface for the catalog. POS, inventory, sales, and reports all read
through ``get_product`` / ``lookup_for_pos`` / ``list_products`` and never
touch the repository directly.

Identifier conventions
======================
* If the caller omits ``barcode``, we generate one: ``"2"`` (in-store EAN
  prefix per GS1) + 12 random digits. Collisions are vanishingly unlikely
  but we still retry on the UNIQUE constraint just in case.
* ``code`` is left to the user — empty is fine.

POS lookup priority (matches legacy behavior)
=============================================
1. exact ``code`` match
2. exact ``barcode`` match
3. exact ``name`` match
This is what the cashier expects when they type/scan a single identifier.
"""

from __future__ import annotations

import logging
import secrets
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import Conflict, NotFound

from app.core.pagination import paginate_offset
from app.extensions import db
from app.modules.products import repository as repo
from app.modules.products.models import Product, ProductCategory
from app.modules.products.schemas import ProductCreate, ProductUpdate


log = logging.getLogger(__name__)


# --- Identifier generation --------------------------------------------------

def _generate_barcode() -> str:
    """In-store EAN-13 style: ``"2"`` prefix + 12 random digits.

    GS1 reserves the ``2`` prefix range for in-store barcodes, so this won't
    collide with manufacturer barcodes scanned from real packaging.
    """
    body = "".join(str(secrets.randbelow(10)) for _ in range(12))
    return "2" + body


# --- Create -----------------------------------------------------------------

def create_product(
    *, tenant_id: uuid.UUID, payload: ProductCreate
) -> Product:
    """Insert a new product. Auto-generates a barcode when missing.

    Raises:
        Conflict: ``code`` or ``barcode`` already used by another product
            in this tenant.
    """
    session = db.session

    if payload.code and repo.code_taken(session, tenant_id=tenant_id, code=payload.code):
        raise Conflict(f"Product code '{payload.code}' is already in use.")

    barcode = payload.barcode
    if not barcode:
        # Retry up to 5 times against the (vanishingly small) collision odds.
        for _ in range(5):
            candidate = _generate_barcode()
            if not repo.barcode_taken(session, tenant_id=tenant_id, barcode=candidate):
                barcode = candidate
                break
        else:
            raise Conflict("Could not allocate a unique barcode; try again.")
    elif repo.barcode_taken(session, tenant_id=tenant_id, barcode=barcode):
        raise Conflict(f"Barcode '{barcode}' is already in use.")

    product = Product(
        tenant_id=tenant_id,
        name=payload.name.strip(),
        name_ar=(payload.name_ar.strip() if payload.name_ar else None),
        category=payload.category,
        code=(payload.code.strip() if payload.code else None),
        barcode=barcode,
        cost=payload.cost,
        price=payload.price,
        reorder_point=payload.reorder_point,
        description=payload.description,
        is_active=True,
    )

    try:
        repo.add(session, product)
    except IntegrityError as exc:
        session.rollback()
        # Race condition: someone created a colliding row between our
        # pre-flight and the flush. Translate to a clean 409.
        raise Conflict("Product code or barcode collided; please retry.") from exc

    log.info(
        "product_created",
        extra={
            "tenant_id": str(tenant_id),
            "product_id": str(product.id),
            "code": product.code,
            "barcode": product.barcode,
        },
    )
    return product


# --- Read -------------------------------------------------------------------

def get_product(*, tenant_id: uuid.UUID, product_id: uuid.UUID) -> Product:
    p = repo.get_by_id(db.session, product_id)
    if p is None or p.tenant_id != tenant_id or p.deleted_at is not None:
        raise NotFound("Product not found.")
    return p


def list_products(
    *,
    tenant_id: uuid.UUID,
    page: int,
    per_page: int,
    category: Optional[ProductCategory] = None,
    search: Optional[str] = None,
    only_active: bool = True,
) -> dict:
    stmt = repo.list_query(
        tenant_id=tenant_id,
        category=category,
        search=search,
        only_active=only_active,
    )
    return paginate_offset(db.session, stmt, page=page, per_page=per_page)


def lookup_for_pos(*, tenant_id: uuid.UUID, query: str) -> Optional[Product]:
    """Single-shot lookup used by the POS scan/type field.

    Priority: ``code`` → ``barcode`` → exact ``name``. Returns ``None`` if
    nothing matches (POS will fall back to a search dropdown).
    """
    q = (query or "").strip()
    if not q:
        return None
    session = db.session
    return (
        repo.get_by_code(session, tenant_id=tenant_id, code=q)
        or repo.get_by_barcode(session, tenant_id=tenant_id, barcode=q)
        or repo.get_by_name_exact(session, tenant_id=tenant_id, name=q)
    )


# --- Update -----------------------------------------------------------------

def update_product(
    *, tenant_id: uuid.UUID, product_id: uuid.UUID, payload: ProductUpdate
) -> Product:
    session = db.session
    product = get_product(tenant_id=tenant_id, product_id=product_id)

    fields = payload.model_dump(exclude_unset=True)

    # Pre-flight uniqueness on code/barcode to give a clean 409.
    new_code = fields.get("code")
    if new_code is not None and new_code != product.code:
        if new_code and repo.code_taken(
            session, tenant_id=tenant_id, code=new_code, exclude_id=product.id
        ):
            raise Conflict(f"Product code '{new_code}' is already in use.")

    new_barcode = fields.get("barcode")
    if new_barcode is not None and new_barcode != product.barcode:
        if new_barcode and repo.barcode_taken(
            session, tenant_id=tenant_id, barcode=new_barcode, exclude_id=product.id
        ):
            raise Conflict(f"Barcode '{new_barcode}' is already in use.")

    for key, value in fields.items():
        setattr(product, key, value)

    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise Conflict("Product update violated a uniqueness constraint.") from exc

    log.info(
        "product_updated",
        extra={"tenant_id": str(tenant_id), "product_id": str(product.id),
               "changed": list(fields.keys())},
    )
    return product


# --- Delete (soft) ----------------------------------------------------------

def delete_product(*, tenant_id: uuid.UUID, product_id: uuid.UUID) -> None:
    """Soft-delete: sets ``deleted_at``. The row stays for audit/history
    (past sales reference it); the UI hides it.

    We do NOT block delete when stock > 0; the warehouse manager has to
    deliberately confirm. The POS won't show deleted products regardless.
    """
    product = get_product(tenant_id=tenant_id, product_id=product_id)
    product.deleted_at = datetime.utcnow()
    product.is_active = False
    db.session.flush()
    log.info(
        "product_deleted",
        extra={"tenant_id": str(tenant_id), "product_id": str(product.id)},
    )
