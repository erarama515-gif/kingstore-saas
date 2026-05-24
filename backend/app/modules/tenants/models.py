"""Tenant ORM model.

A ``Tenant`` represents one customer organization (one shop or one business
group). It is **not** itself tenant-scoped — it's the root that other tables
point to via ``tenant_id``.

F1 keeps this minimal: enough columns to be useful in development and to seed
the first Alembic migration. Billing/subscription/plan columns land in F13.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Enum, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import Base, SoftDeleteMixin, TimestampMixin, uuid_pk


class TenantStatus(str, enum.Enum):
    trial = "trial"
    active = "active"
    suspended = "suspended"
    canceled = "canceled"


class Tenant(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = uuid_pk()

    # Short URL-safe identifier (e.g. "kingstore-cairo"). Unique across all
    # tenants. Used in invitation links and subdomain routing later.
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)

    name: Mapped[str] = mapped_column(String(200), nullable=False)

    status: Mapped[TenantStatus] = mapped_column(
        Enum(TenantStatus, name="tenant_status"),
        nullable=False,
        default=TenantStatus.trial,
        server_default=TenantStatus.trial.value,
    )

    # Default branch for users that don't have an explicit assignment. Nullable
    # because at signup time the default branch is created in the same txn.
    default_branch_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    trial_ends_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - dev convenience
        return f"<Tenant {self.slug} ({self.status.value})>"
