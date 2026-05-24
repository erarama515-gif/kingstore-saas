"""Branch ORM model.

A branch is a physical store location. Inventory, sales, expenses, and most
operational records are scoped to a branch. Customers and Suppliers are
tenant-scoped (shared across branches by default).
"""

from __future__ import annotations

import uuid

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import Base, SoftDeleteMixin, TenantScopedMixin, TimestampMixin, uuid_pk


class Branch(Base, TimestampMixin, SoftDeleteMixin, TenantScopedMixin):
    __tablename__ = "branches"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_branches_tenant_code"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Branch {self.code} ({self.tenant_id})>"
