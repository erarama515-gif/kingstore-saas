"""Inventory ORM models.

Tables
======

* ``stock_levels``    — current quantity per ``(product_id, branch_id)``.
                        A *materialized* snapshot maintained transactionally
                        by the service layer (one row per product per branch).
* ``stock_movements`` — append-only audit log. Every change to a stock_level
                        produces exactly one movement row. Immutable.

Why both
========
StockLevel makes "how much do we have *now*" a fast UNIQUE-row SELECT.
StockMovement gives you the reason behind every quantity change — required
for audits and for re-deriving balances from scratch when something looks
off. They must be written together inside the same DB transaction; the
service enforces that.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    Date,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db.base import Base, TenantScopedMixin, TimestampMixin, uuid_pk


# --- Enums ------------------------------------------------------------------

class MovementType(str, enum.Enum):
    """Why this movement happened. Direction (+/-) is implied by the type."""

    # +qty
    purchase = "purchase"               # received from supplier
    return_in = "return_in"             # customer returned an item
    transfer_in = "transfer_in"         # arrived from another branch
    adjustment_in = "adjustment_in"     # opening stock / found inventory
    # -qty
    sale = "sale"                       # sold via POS
    return_out = "return_out"           # returned to supplier
    transfer_out = "transfer_out"       # shipped to another branch
    adjustment_out = "adjustment_out"   # damage / theft / shrinkage
    repair_consumption = "repair_consumption"  # parts used in a repair

    @property
    def is_inbound(self) -> bool:
        return self in (
            MovementType.purchase,
            MovementType.return_in,
            MovementType.transfer_in,
            MovementType.adjustment_in,
        )


# --- StockLevel -------------------------------------------------------------

class StockLevel(Base, TimestampMixin, TenantScopedMixin):
    """Current quantity of a product at one branch.

    The (product_id, branch_id) pair is UNIQUE — there is at most one row
    per combination, and the service is responsible for upserting it.

    Note: ``qty_on_hand >= 0`` is enforced by CHECK constraint. The service
    locks the row with ``SELECT ... FOR UPDATE`` before modifying it, so
    two concurrent decrements on the last unit cannot both succeed.
    """

    __tablename__ = "stock_levels"
    __table_args__ = (
        UniqueConstraint("product_id", "branch_id", name="uq_stock_levels_product_branch"),
        CheckConstraint("qty_on_hand >= 0", name="ck_stock_levels_qty_nonneg"),
        Index("ix_stock_levels_tenant_product", "tenant_id", "product_id"),
        Index("ix_stock_levels_tenant_branch", "tenant_id", "branch_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("branches.id", ondelete="RESTRICT"),
        nullable=False,
    )

    qty_on_hand: Mapped[int] = mapped_column(
        nullable=False, default=0, server_default="0"
    )

    # Optional running average cost (weighted by inbound movements). For MVP
    # we maintain it on every inbound but the sale path still uses the
    # Product.cost snapshot for COGS; switching to avg_cost is a one-line
    # change in the sale service later.
    avg_cost: Mapped[Decimal] = mapped_column(
        Numeric(14, 4), nullable=False, default=Decimal("0"), server_default="0"
    )

    product = relationship("Product", lazy="joined")
    branch = relationship("Branch", lazy="joined")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<StockLevel p={self.product_id} b={self.branch_id} qty={self.qty_on_hand}>"


# --- StockMovement ----------------------------------------------------------

class StockMovement(Base, TenantScopedMixin):
    """One stock change. Append-only — never UPDATE or DELETE these rows.

    Reverses are modeled as a *new* movement of the opposite type that
    points back via ``reverses_id``.
    """

    __tablename__ = "stock_movements"
    __table_args__ = (
        CheckConstraint("qty > 0", name="ck_stock_movements_qty_positive"),
        CheckConstraint("unit_cost >= 0", name="ck_stock_movements_unit_cost_nonneg"),
        Index("ix_stock_movements_tenant_product_date", "tenant_id", "product_id", "movement_date"),
        Index("ix_stock_movements_tenant_branch_date", "tenant_id", "branch_id", "movement_date"),
        Index("ix_stock_movements_reference", "tenant_id", "reference"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("branches.id", ondelete="RESTRICT"),
        nullable=False,
    )

    movement_type: Mapped[MovementType] = mapped_column(
        Enum(MovementType, name="movement_type"), nullable=False
    )

    # Always positive — direction is encoded in movement_type.
    qty: Mapped[int] = mapped_column(nullable=False)

    # Unit cost at the time of movement. For inbound movements (purchase /
    # return_in / adjustment_in) this is the actual cost paid; for outbound
    # movements it's the snapshot of avg_cost (or Product.cost) at the time
    # the line was posted.
    unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(14, 4), nullable=False, default=Decimal("0"), server_default="0"
    )

    movement_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Free-form back-reference to the originating row (e.g. ``sale:<uuid>``,
    # ``purchase:<uuid>``, ``manual:<reason>``). Used by reports to hop back
    # to the source.
    reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Optional reversal link (a counter-movement points at the original).
    reverses_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stock_movements.id", ondelete="RESTRICT"),
        nullable=True,
    )

    # Optional journal-entry link so dashboards can show "this purchase
    # produced these accounting effects".
    journal_entry_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("journal_entries.id", ondelete="SET NULL"),
        nullable=True,
    )

    notes: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    product = relationship("Product", lazy="joined")
    branch = relationship("Branch", lazy="joined")

    def __repr__(self) -> str:  # pragma: no cover
        sign = "+" if self.movement_type.is_inbound else "-"
        return f"<StockMovement {self.movement_type.value} {sign}{self.qty} p={self.product_id}>"
