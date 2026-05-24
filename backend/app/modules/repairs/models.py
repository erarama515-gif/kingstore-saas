"""Repairs ORM model."""

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
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import Base, SoftDeleteMixin, TenantScopedMixin, TimestampMixin, uuid_pk


class RepairStatus(str, enum.Enum):
    received = "received"
    in_progress = "in_progress"
    done = "done"
    delivered = "delivered"
    canceled = "canceled"


class RepairTicket(Base, TimestampMixin, SoftDeleteMixin, TenantScopedMixin):
    __tablename__ = "repair_tickets"
    __table_args__ = (
        UniqueConstraint("tenant_id", "ticket_number", name="uq_repair_tickets_tenant_number"),
        CheckConstraint("estimated_cost >= 0", name="ck_repair_tickets_estimated_nonneg"),
        CheckConstraint("actual_cost >= 0", name="ck_repair_tickets_actual_nonneg"),
        Index("ix_repair_tickets_tenant_status", "tenant_id", "status"),
        Index("ix_repair_tickets_tenant_date_in", "tenant_id", "date_in"),
        Index("ix_repair_tickets_branch", "branch_id"),
        Index("ix_repair_tickets_customer", "customer_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()

    ticket_number: Mapped[str] = mapped_column(String(30), nullable=False)

    branch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("branches.id", ondelete="RESTRICT"),
        nullable=False,
    )

    customer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=True,
    )
    customer_name: Mapped[str] = mapped_column(String(200), nullable=False)
    customer_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    device_model: Mapped[str] = mapped_column(String(200), nullable=False)
    imei: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    problem: Mapped[str] = mapped_column(String(500), nullable=False)

    estimated_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0"), server_default="0")
    actual_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0"), server_default="0")

    status: Mapped[RepairStatus] = mapped_column(
        Enum(RepairStatus, name="repair_status"),
        nullable=False,
        default=RepairStatus.received,
        server_default=RepairStatus.received.value,
    )

    date_in: Mapped[date] = mapped_column(Date, nullable=False)
    date_delivered: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    is_paid_on_delivery: Mapped[bool] = mapped_column(
        nullable=False, default=True, server_default="true"
    )

    notes: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    technician_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    delivery_journal_entry_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("journal_entries.id", ondelete="SET NULL"),
        nullable=True,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<RepairTicket {self.ticket_number} {self.device_model} {self.status.value}>"
