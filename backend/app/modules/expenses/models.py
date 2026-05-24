"""Expense ORM model.

An ``Expense`` is the *record* of a real-world outflow. The journal entry it
posts is the financial truth; this table holds the operational metadata
(category, vendor description, who recorded it) so the UI can show a clean
expenses page without having to interpret raw journal lines.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import Base, SoftDeleteMixin, TenantScopedMixin, TimestampMixin, uuid_pk


class Expense(Base, TimestampMixin, SoftDeleteMixin, TenantScopedMixin):
    __tablename__ = "expenses"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_expenses_amount_positive"),
        Index("ix_expenses_tenant_date", "tenant_id", "expense_date"),
        Index("ix_expenses_branch", "branch_id"),
        Index("ix_expenses_account", "expense_account_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()

    branch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("branches.id", ondelete="RESTRICT"),
        nullable=False,
    )

    expense_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Which expense account to charge (one of the 5xxx accounts).
    expense_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Paid from: cash | bank. (Credit purchases from suppliers are a
    # separate flow — purchases module — and shouldn't be expenses.)
    payment_method: Mapped[str] = mapped_column(
        String(20), nullable=False, default="cash", server_default="cash"
    )

    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    description: Mapped[str] = mapped_column(String(300), nullable=False)
    reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Linked journal entry — set after the entry is posted.
    journal_entry_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("journal_entries.id", ondelete="SET NULL"),
        nullable=True,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Expense {self.description} {self.amount}>"
