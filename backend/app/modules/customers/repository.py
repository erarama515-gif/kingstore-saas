"""Customers data access."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.modules.customers.models import Customer


# --- Reads ------------------------------------------------------------------

def get_by_id(session: Session, customer_id: uuid.UUID) -> Optional[Customer]:
    return session.get(Customer, customer_id)


def get_by_phone(
    session: Session, *, tenant_id: uuid.UUID, phone: str
) -> Optional[Customer]:
    return session.execute(
        select(Customer).where(
            Customer.tenant_id == tenant_id,
            Customer.phone == phone,
            Customer.deleted_at.is_(None),
        )
    ).scalar_one_or_none()


def get_by_email(
    session: Session, *, tenant_id: uuid.UUID, email: str
) -> Optional[Customer]:
    return session.execute(
        select(Customer).where(
            Customer.tenant_id == tenant_id,
            Customer.email == email,
            Customer.deleted_at.is_(None),
        )
    ).scalar_one_or_none()


def list_query(
    *,
    tenant_id: uuid.UUID,
    search: Optional[str] = None,
    only_active: bool = True,
    only_with_debt: bool = False,
) -> Select:
    stmt = select(Customer).where(
        Customer.tenant_id == tenant_id,
        Customer.deleted_at.is_(None),
    )
    if only_active:
        stmt = stmt.where(Customer.is_active.is_(True))
    if only_with_debt:
        stmt = stmt.where(Customer.debt_cached > 0)
    if search:
        like = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                Customer.name.ilike(like),
                Customer.name_ar.ilike(like),
                Customer.phone.ilike(like),
                Customer.email.ilike(like),
            )
        )
    return stmt.order_by(Customer.name)


def quick_lookup_query(
    *,
    tenant_id: uuid.UUID,
    query: str,
    limit: int = 10,
) -> Select:
    """POS-shaped lookup: phone exact-prefix first, then name substring."""
    q = query.strip()
    like_prefix = f"{q}%"
    like_any = f"%{q}%"
    stmt = select(Customer).where(
        Customer.tenant_id == tenant_id,
        Customer.deleted_at.is_(None),
        Customer.is_active.is_(True),
        or_(
            Customer.phone.ilike(like_any),
            Customer.name.ilike(like_any),
            Customer.name_ar.ilike(like_any),
        ),
    ).order_by(
        # Phone prefix match first (cashier typing customer's number)
        Customer.phone.ilike(like_prefix).desc(),
        Customer.name,
    ).limit(limit)
    return stmt


def phone_taken(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    phone: str,
    exclude_id: Optional[uuid.UUID] = None,
) -> bool:
    stmt = select(func.count()).select_from(Customer).where(
        Customer.tenant_id == tenant_id,
        Customer.phone == phone,
        Customer.deleted_at.is_(None),
    )
    if exclude_id:
        stmt = stmt.where(Customer.id != exclude_id)
    return (session.execute(stmt).scalar_one() or 0) > 0


def email_taken(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    email: str,
    exclude_id: Optional[uuid.UUID] = None,
) -> bool:
    stmt = select(func.count()).select_from(Customer).where(
        Customer.tenant_id == tenant_id,
        Customer.email == email,
        Customer.deleted_at.is_(None),
    )
    if exclude_id:
        stmt = stmt.where(Customer.id != exclude_id)
    return (session.execute(stmt).scalar_one() or 0) > 0


# --- Writes -----------------------------------------------------------------

def add(session: Session, customer: Customer) -> Customer:
    session.add(customer)
    session.flush()
    return customer
