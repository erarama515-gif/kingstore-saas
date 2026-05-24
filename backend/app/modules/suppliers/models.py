"""Supplier ORM model.

Tenant-scoped. Symmetric to ``Customer`` but represents money the system
owes (AP). The same NULL-aware uniqueness applies to phone/email so cash
vendors without details can still be recorded.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import Base, SoftDeleteMixin, TenantScopedMixin, TimestampMixin, uuid_pk


class Supplier(Base, TimestampMixin, SoftDeleteMixin, TenantScopedMixin):
    __tablename__ = "suppliers"
    __table_args__ = (
        Index(
            "uq_suppliers_tenant_phone",
            "tenant_id", "phone",
            unique=True,
            postgresql_where="phone IS NOT NULL",
        ),
        Index(
            "uq_suppliers_tenant_email",
            "tenant_id", "email",
            unique=True,
            postgresql_where="email IS NOT NULL",
        ),
        Index("ix_suppliers_tenant_name", "tenant_id", "name"),
        CheckConstraint(
            "total_purchased_cached >= 0",
            name="ck_suppliers_total_purchased_nonneg",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    name_ar: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    contact_person: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

    # Cached aggregates — kept in sync by purchase / payment services.
    # Source of truth lives in the journal (AP account lines tagged with
    # this supplier's id).
    total_purchased_cached: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0"), server_default="0"
    )
    payable_cached: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0"), server_default="0"
    )
    last_txn_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    is_active: Mapped[bool] = mapped_column(
        nullable=False, default=True, server_default="true"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Supplier {self.name}>"
