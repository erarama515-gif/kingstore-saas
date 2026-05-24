"""Inventory data access."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.modules.inventory.models import StockLevel, StockMovement


# --- StockLevel reads -------------------------------------------------------

def get_level(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    product_id: uuid.UUID,
    branch_id: uuid.UUID,
    for_update: bool = False,
) -> Optional[StockLevel]:
    """Fetch a single stock level row.

    When ``for_update=True``, locks the row (``SELECT ... FOR UPDATE``) so
    concurrent decrements serialize through Postgres. Required for the
    sale / adjustment paths to be atomic.
    """
    stmt = select(StockLevel).where(
        StockLevel.tenant_id == tenant_id,
        StockLevel.product_id == product_id,
        StockLevel.branch_id == branch_id,
    )
    if for_update:
        stmt = stmt.with_for_update()
    return session.execute(stmt).scalar_one_or_none()


def list_levels_query(
    *,
    tenant_id: uuid.UUID,
    branch_id: Optional[uuid.UUID] = None,
    only_with_stock: bool = False,
    only_low_stock: bool = False,
) -> Select:
    """Select StockLevel rows with optional filters. Caller paginates."""
    from app.modules.products.models import Product  # local to avoid cycle
    stmt = (
        select(StockLevel)
        .join(Product, Product.id == StockLevel.product_id)
        .where(StockLevel.tenant_id == tenant_id, Product.deleted_at.is_(None))
        .order_by(Product.name)
    )
    if branch_id is not None:
        stmt = stmt.where(StockLevel.branch_id == branch_id)
    if only_with_stock:
        stmt = stmt.where(StockLevel.qty_on_hand > 0)
    if only_low_stock:
        stmt = stmt.where(StockLevel.qty_on_hand <= Product.reorder_point)
    return stmt


# --- StockMovement reads ----------------------------------------------------

def list_movements_query(
    *,
    tenant_id: uuid.UUID,
    product_id: Optional[uuid.UUID] = None,
    branch_id: Optional[uuid.UUID] = None,
    date_from=None,
    date_to=None,
) -> Select:
    stmt = (
        select(StockMovement)
        .where(StockMovement.tenant_id == tenant_id)
        .order_by(StockMovement.movement_date.desc(), StockMovement.id.desc())
    )
    if product_id is not None:
        stmt = stmt.where(StockMovement.product_id == product_id)
    if branch_id is not None:
        stmt = stmt.where(StockMovement.branch_id == branch_id)
    if date_from is not None:
        stmt = stmt.where(StockMovement.movement_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(StockMovement.movement_date <= date_to)
    return stmt


# --- Writes -----------------------------------------------------------------

def add_level(session: Session, level: StockLevel) -> StockLevel:
    session.add(level)
    session.flush()
    return level


def add_movement(session: Session, movement: StockMovement) -> StockMovement:
    session.add(movement)
    session.flush()
    return movement
