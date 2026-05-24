"""Sales data access."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Optional

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.modules.sales.models import Sale, SaleLine, SalePayment


def get_sale(session: Session, sale_id: uuid.UUID) -> Optional[Sale]:
    return session.get(Sale, sale_id)


def add(session: Session, obj):
    session.add(obj)
    session.flush()
    return obj


def list_sales_query(
    *,
    tenant_id: uuid.UUID,
    branch_id: Optional[uuid.UUID] = None,
    customer_id: Optional[uuid.UUID] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    only_unpaid: bool = False,
) -> Select:
    stmt = (
        select(Sale)
        .where(
            Sale.tenant_id == tenant_id,
            Sale.deleted_at.is_(None),
        )
        .order_by(Sale.sale_date.desc(), Sale.created_at.desc())
    )
    if branch_id is not None:
        stmt = stmt.where(Sale.branch_id == branch_id)
    if customer_id is not None:
        stmt = stmt.where(Sale.customer_id == customer_id)
    if date_from is not None:
        stmt = stmt.where(Sale.sale_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(Sale.sale_date <= date_to)
    if only_unpaid:
        stmt = stmt.where(Sale.is_paid.is_(False))
    return stmt


def next_sale_number(session: Session, *, tenant_id: uuid.UUID) -> str:
    """Compute the next ``INV-NNNNNN`` for this tenant.

    Strategy: COUNT(*) + 1, zero-padded to 6 digits. Under heavy concurrency
    two simultaneous sales might propose the same number — the
    ``uq_sales_tenant_number`` constraint forces a retry. The service catches
    IntegrityError and re-tries with COUNT+2.
    """
    cnt = session.execute(
        select(func.count()).select_from(Sale).where(Sale.tenant_id == tenant_id)
    ).scalar_one()
    return f"INV-{(cnt + 1):06d}"


def sum_payments_for_sale(session: Session, sale_id: uuid.UUID) -> "Decimal":
    from decimal import Decimal as D
    val = session.execute(
        select(func.coalesce(func.sum(SalePayment.amount), 0)).where(
            SalePayment.sale_id == sale_id
        )
    ).scalar_one()
    return D(val)
