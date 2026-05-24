"""DeviceInstance ORM — one row per physical phone / serialized item.

Identity
========
Either ``imei`` or ``serial_number`` is required. Both are UNIQUE per tenant
when present (NULL allowed but duplicates forbidden via a partial index in
the migration). 15-digit IMEI is the standard for phones; ``serial_number``
covers everything else.

Lifecycle
=========
Status transitions are enforced at the service layer:
    in_stock → sold | damaged | archived
    sold → under_repair | returned
    under_repair → sold (back to owner) | damaged
    returned → in_stock | damaged
    damaged → archived
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db.base import Base, SoftDeleteMixin, TenantScopedMixin, TimestampMixin, uuid_pk


class DeviceStatus(str, enum.Enum):
    """Lifecycle state. See module docstring for transition rules."""

    in_stock = "in_stock"
    sold = "sold"
    under_repair = "under_repair"
    returned = "returned"
    damaged = "damaged"
    archived = "archived"


class DeviceInstance(Base, TimestampMixin, SoftDeleteMixin, TenantScopedMixin):
    __tablename__ = "device_instances"
    __table_args__ = (
        # Uniqueness is per-tenant. IMEI and serial are both nullable but
        # if present, must be unique within the tenant. The migration creates
        # partial unique indexes (WHERE imei IS NOT NULL).
        UniqueConstraint("tenant_id", "imei", name="uq_device_instances_tenant_imei"),
        UniqueConstraint("tenant_id", "serial_number", name="uq_device_instances_tenant_serial"),
        CheckConstraint(
            "imei IS NOT NULL OR serial_number IS NOT NULL",
            name="ck_device_instances_id_required",
        ),
        Index("ix_device_instances_status", "tenant_id", "status"),
        Index("ix_device_instances_customer", "tenant_id", "customer_id"),
        Index("ix_device_instances_product", "tenant_id", "product_id"),
        Index("ix_device_instances_imei", "tenant_id", "imei"),
        Index("ix_device_instances_serial", "tenant_id", "serial_number"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    product = relationship("Product", lazy="joined")

    # Current branch — where the device physically is. Null = sold/archived.
    branch_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("branches.id", ondelete="RESTRICT"),
        nullable=True,
    )

    imei: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    serial_number: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)

    status: Mapped[DeviceStatus] = mapped_column(
        Enum(DeviceStatus, name="device_status"),
        nullable=False,
        default=DeviceStatus.in_stock,
        server_default=DeviceStatus.in_stock.value,
    )

    # Current owner if status=sold (or under_repair on behalf of an owner)
    customer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=True,
    )

    # Linkage to the originating sale. Plain UUID (no FK) so we can soft-link
    # without circular schema concerns.
    sale_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    sale_line_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    sold_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Warranty (derived at sale time from product.warranty_period_days, but
    # stored here so it survives product config changes)
    warranty_ends_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # The cost the unit was purchased at — useful for per-device P&L
    purchase_cost: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0"), server_default="0"
    )

    notes: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    def identifier(self) -> str:
        return self.imei or self.serial_number or str(self.id)

    @property
    def is_under_warranty(self) -> bool:
        return self.warranty_ends_at is not None and self.warranty_ends_at >= date.today()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<DeviceInstance {self.identifier()} {self.status.value}>"
