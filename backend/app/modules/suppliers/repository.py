"""Suppliers data access."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.modules.suppliers.models import Supplier


def get_by_id(session: Session, supplier_id: uuid.UUID) -> Optional[Supplier]:
    return session.get(Supplier, supplier_id)


def get_by_phone(
    session: Session, *, tenant_id: uuid.UUID, phone: str
) -> Optional[Supplier]:
    return session.execute(
        select(Supplier).where(
            Supplier.tenant_id == tenant_id,
            Supplier.phone == phone,
            Supplier.deleted_at.is_(None),
        )
    ).scalar_one_or_none()


def list_query(
    *,
    tenant_id: uuid.UUID,
    search: Optional[str] = None,
    only_active: bool = True,
    only_with_payable: bool = False,
) -> Select:
    stmt = select(Supplier).where(
        Supplier.tenant_id == tenant_id,
        Supplier.deleted_at.is_(None),
    )
    if only_active:
        stmt = stmt.where(Supplier.is_active.is_(True))
    if only_with_payable:
        stmt = stmt.where(Supplier.payable_cached > 0)
    if search:
        like = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                Supplier.name.ilike(like),
                Supplier.name_ar.ilike(like),
                Supplier.phone.ilike(like),
                Supplier.email.ilike(like),
                Supplier.contact_person.ilike(like),
            )
        )
    return stmt.order_by(Supplier.name)


def quick_lookup_query(
    *, tenant_id: uuid.UUID, query: str, limit: int = 10
) -> Select:
    q = query.strip()
    like_any = f"%{q}%"
    return select(Supplier).where(
        Supplier.tenant_id == tenant_id,
        Supplier.deleted_at.is_(None),
        Supplier.is_active.is_(True),
        or_(
            Supplier.name.ilike(like_any),
            Supplier.name_ar.ilike(like_any),
            Supplier.phone.ilike(like_any),
        ),
    ).order_by(Supplier.name).limit(limit)


def phone_taken(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    phone: str,
    exclude_id: Optional[uuid.UUID] = None,
) -> bool:
    stmt = select(func.count()).select_from(Supplier).where(
        Supplier.tenant_id == tenant_id,
        Supplier.phone == phone,
        Supplier.deleted_at.is_(None),
    )
    if exclude_id:
        stmt = stmt.where(Supplier.id != exclude_id)
    return (session.execute(stmt).scalar_one() or 0) > 0


def email_taken(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    email: str,
    exclude_id: Optional[uuid.UUID] = None,
) -> bool:
    stmt = select(func.count()).select_from(Supplier).where(
        Supplier.tenant_id == tenant_id,
        Supplier.email == email,
        Supplier.deleted_at.is_(None),
    )
    if exclude_id:
        stmt = stmt.where(Supplier.id != exclude_id)
    return (session.execute(stmt).scalar_one() or 0) > 0


def add(session: Session, supplier: Supplier) -> Supplier:
    session.add(supplier)
    session.flush()
    return supplier
