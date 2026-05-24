"""Treasury ORM model — day-close snapshots."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import Base, TenantScopedMixin, TimestampMixin, uuid_pk


class DayClose(Base, TimestampMixin, TenantScopedMixin):
    """Snapshot taken when the cashier closes the day at a branch.

    Stores both the *expected* (computed from the ledger) and *counted*
    (what the cashier physically counted) cash, plus the variance. The
    variance is the operational truth shop owners care about.

    Idempotency: one close per ``(tenant_id, branch_id, business_date)``.
    """

    __tablename__ = "day_closes"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "branch_id", "business_date",
            name="uq_day_closes_tenant_branch_date",
        ),
        CheckConstraint("counted_cash >= 0", name="ck_day_closes_counted_nonneg"),
        Index("ix_day_closes_tenant_date", "tenant_id", "business_date"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()

    branch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("branches.id", ondelete="RESTRICT"),
        nullable=False,
    )

    business_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Cash totals at close
    opening_cash: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0"))
    cash_in: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0"))
    cash_out: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0"))
    expected_cash: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0"))
    counted_cash: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0"))
    variance: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0"))

    notes: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    closed_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    closed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
