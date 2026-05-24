"""Customer ORM model.

Tenant-scoped. Customers are shared across branches (one customer who shops
at branch A might also walk into branch B); the legacy app's behavior.

Phone uniqueness
================
``phone`` is NULLABLE so walk-in customers can be recorded without one
(the legacy app required it, which awkwardly forced cashiers to invent
placeholders). When present, phone is UNIQUE per tenant — the partial
UNIQUE index is declared explicitly so NULLs don't collide with each other.

Cached vs. authoritative fields
===============================
``total_spent_cached``, ``debt_cached``, ``visits_count``, ``last_txn_at`` are
**denormalized caches** maintained by the sales/payment services for fast UI
rendering. The journal ledger is authoritative — ``service.customer_balance``
recomputes from the AR account lines tagged with this customer's id.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import Base, SoftDeleteMixin, TenantScopedMixin, TimestampMixin, uuid_pk


class Customer(Base, TimestampMixin, SoftDeleteMixin, TenantScopedMixin):
    __tablename__ = "customers"
    __table_args__ = (
        # Partial UNIQUE: only enforce when phone is provided.
        Index(
            "uq_customers_tenant_phone",
            "tenant_id", "phone",
            unique=True,
            postgresql_where="phone IS NOT NULL",
        ),
        # Email also partially unique per tenant (NULL allowed for many).
        Index(
            "uq_customers_tenant_email",
            "tenant_id", "email",
            unique=True,
            postgresql_where="email IS NOT NULL",
        ),
        # Searchable indexes
        Index("ix_customers_tenant_name", "tenant_id", "name"),
        CheckConstraint(
            "total_spent_cached >= 0", name="ck_customers_total_spent_nonneg"
        ),
        CheckConstraint("visits_count >= 0", name="ck_customers_visits_nonneg"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    name_ar: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

    # Cached aggregates — kept in sync by sales / payment services.
    # Source of truth lives in the journal (AR account lines tagged with
    # this customer's id). UI may read from cache for speed; reports / aging
    # queries should hit the ledger.
    total_spent_cached: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0"), server_default="0"
    )
    debt_cached: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0"), server_default="0"
    )
    visits_count: Mapped[int] = mapped_column(
        nullable=False, default=0, server_default="0"
    )
    last_txn_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    is_active: Mapped[bool] = mapped_column(
        nullable=False, default=True, server_default="true"
    )

    def __repr__(self) -> str:  # pragma: no cover
        ident = self.phone or self.email or self.name
        return f"<Customer {ident}>"
