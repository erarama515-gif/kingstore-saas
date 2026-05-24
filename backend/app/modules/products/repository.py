"""Products data access.

Repository = thin DB layer. No business rules, no auto-generation, no
side effects. Just queries + writes + the simple existence checks that
need to live close to the SQL.
"""

from __future__ import annotations

import uuid
from typing import Optional, Sequence

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.modules.products.models import Product, ProductCategory


# --- Reads ------------------------------------------------------------------

def get_by_id(session: Session, product_id: uuid.UUID) -> Optional[Product]:
    return session.get(Product, product_id)


def get_by_ids(
    session: Session, *, tenant_id: uuid.UUID, ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, Product]:
    if not ids:
        return {}
    rows = session.execute(
        select(Product).where(
            Product.tenant_id == tenant_id,
            Product.id.in_(list(ids)),
            Product.deleted_at.is_(None),
        )
    ).scalars().all()
    return {p.id: p for p in rows}


def get_by_code(
    session: Session, *, tenant_id: uuid.UUID, code: str
) -> Optional[Product]:
    return session.execute(
        select(Product).where(
            Product.tenant_id == tenant_id,
            Product.code == code,
            Product.deleted_at.is_(None),
        )
    ).scalar_one_or_none()


def get_by_barcode(
    session: Session, *, tenant_id: uuid.UUID, barcode: str
) -> Optional[Product]:
    return session.execute(
        select(Product).where(
            Product.tenant_id == tenant_id,
            Product.barcode == barcode,
            Product.deleted_at.is_(None),
        )
    ).scalar_one_or_none()


def get_by_name_exact(
    session: Session, *, tenant_id: uuid.UUID, name: str
) -> Optional[Product]:
    """Used by POS lookup when scanning doesn't apply (cashier types name)."""
    return session.execute(
        select(Product).where(
            Product.tenant_id == tenant_id,
            Product.name == name,
            Product.deleted_at.is_(None),
        )
    ).scalar_one_or_none()


def list_query(
    *,
    tenant_id: uuid.UUID,
    category: Optional[ProductCategory] = None,
    search: Optional[str] = None,
    only_active: bool = True,
) -> Select:
    """Return a Select for ``Product`` matching the given filters.

    Caller paginates via :func:`app.core.pagination.paginate_offset`.
    """
    stmt = select(Product).where(
        Product.tenant_id == tenant_id,
        Product.deleted_at.is_(None),
    )
    if only_active:
        stmt = stmt.where(Product.is_active.is_(True))
    if category is not None:
        stmt = stmt.where(Product.category == category)
    if search:
        like = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                Product.name.ilike(like),
                Product.name_ar.ilike(like),
                Product.code.ilike(like),
                Product.barcode.ilike(like),
            )
        )
    return stmt.order_by(Product.name)


def code_taken(
    session: Session, *, tenant_id: uuid.UUID, code: str, exclude_id: Optional[uuid.UUID] = None
) -> bool:
    stmt = select(func.count()).select_from(Product).where(
        Product.tenant_id == tenant_id,
        Product.code == code,
        Product.deleted_at.is_(None),
    )
    if exclude_id:
        stmt = stmt.where(Product.id != exclude_id)
    return (session.execute(stmt).scalar_one() or 0) > 0


def barcode_taken(
    session: Session, *, tenant_id: uuid.UUID, barcode: str, exclude_id: Optional[uuid.UUID] = None
) -> bool:
    stmt = select(func.count()).select_from(Product).where(
        Product.tenant_id == tenant_id,
        Product.barcode == barcode,
        Product.deleted_at.is_(None),
    )
    if exclude_id:
        stmt = stmt.where(Product.id != exclude_id)
    return (session.execute(stmt).scalar_one() or 0) > 0


# --- Writes -----------------------------------------------------------------

def add(session: Session, product: Product) -> Product:
    session.add(product)
    session.flush()
    return product
