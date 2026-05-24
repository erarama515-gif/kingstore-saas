"""Product ORM model.

Product is the *catalog entity*: name, identifiers, standard cost + sale
price. Stock-on-hand and stock movements live in the ``inventory`` module
keyed by ``product_id``.

Identifiers
===========
* ``code``    — short human typeable SKU (e.g. ``MOB123``). UNIQUE per tenant.
* ``barcode`` — full numeric barcode (EAN-13 style, auto-generated when not
                supplied). UNIQUE per tenant.

The legacy app collapsed both into one field with chained fallbacks; we
preserve the same lookup priority in the service layer.
"""

from __future__ import annotations

import enum
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import CheckConstraint, Enum, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import Base, SoftDeleteMixin, TenantScopedMixin, TimestampMixin, uuid_pk


class ProductCategory(str, enum.Enum):
    """Top-level categorization. Mirrors the legacy app's three buckets so
    the existing data migrates cleanly. Free-text ``tags`` come later."""

    mobile = "mobile"
    accessory = "accessory"
    spare = "spare"
    service = "service"  # services have a price but no stock (treated as
                         # non-tracked items in the inventory module).
    other = "other"


class Product(Base, TimestampMixin, SoftDeleteMixin, TenantScopedMixin):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("tenant_id", "barcode", name="uq_products_tenant_barcode"),
        UniqueConstraint("tenant_id", "code", name="uq_products_tenant_code"),
        CheckConstraint("cost >= 0", name="ck_products_cost_nonneg"),
        CheckConstraint("price >= 0", name="ck_products_price_nonneg"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()

    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    name_ar: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    category: Mapped[ProductCategory] = mapped_column(
        Enum(ProductCategory, name="product_category"),
        nullable=False,
        default=ProductCategory.other,
        server_default=ProductCategory.other.value,
    )

    # Optional human-friendly SKU (e.g. "MOB123"). Some shops type the code
    # at POS instead of scanning, so we expose both.
    code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Full numeric barcode (EAN-13). Auto-generated when caller omits it.
    barcode: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Standard cost — used as the COGS snapshot on sale (until we implement
    # weighted-average per StockLevel in a later phase).
    cost: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0"), server_default="0"
    )
    price: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0"), server_default="0"
    )

    # Low-stock alert threshold (used by dashboards / reports).
    reorder_point: Mapped[int] = mapped_column(
        nullable=False, default=0, server_default="0"
    )

    # Per-unit IMEI/Serial tracking. Phones flip ``track_by_imei`` on; other
    # serialized goods (laptops, cameras) flip ``track_by_serial``. Both off
    # for normal accessories — those remain pure inventory items.
    track_by_imei: Mapped[bool] = mapped_column(
        nullable=False, default=False, server_default="false"
    )
    track_by_serial: Mapped[bool] = mapped_column(
        nullable=False, default=False, server_default="false"
    )
    # Default warranty granted to the buyer at point of sale, in days.
    # Snapshotted onto the DeviceInstance at sale time so later config
    # changes don't retroactively alter past warranties.
    warranty_period_days: Mapped[int] = mapped_column(
        nullable=False, default=0, server_default="0"
    )

    # When False the product is hidden from POS but kept for historical
    # references. Soft-delete via ``deleted_at`` is reserved for "this product
    # never should have existed" cases.
    is_active: Mapped[bool] = mapped_column(
        nullable=False, default=True, server_default="true"
    )

    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    @property
    def is_tracked(self) -> bool:
        """True if this product requires per-unit identity tracking."""
        return bool(self.track_by_imei or self.track_by_serial)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Product {self.code or self.barcode or self.name}>"
