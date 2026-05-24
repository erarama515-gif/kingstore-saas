"""Accounting ORM models.

Tables
======

* ``accounts``         — Chart of Accounts. Hierarchical (parent_id self-FK).
* ``journal_entries``  — Header row per accounting event.
* ``journal_lines``    — One row per debit or credit. ``debit XOR credit > 0``.

Integrity invariants
====================

* ``Numeric(14, 2)`` for all amounts — never float.
* ``debit >= 0`` and ``credit >= 0`` and exactly one is non-zero per line
  (enforced by CHECK constraint).
* Per-entry ``Σ debit = Σ credit`` is enforced at the *service* layer inside
  the same transaction. The DB has no SUM-check trigger because that would
  require deferrable constraints and add complexity for marginal safety —
  the service is the only writer, and it has a unit test.
* Once a JournalEntry has a ``posted_at`` timestamp, its lines are immutable.
  Corrections happen via ``reverse_journal_entry`` which posts a counter-entry.
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

from app.core.db.base import Base, TenantScopedMixin, TimestampMixin, uuid_pk


# --- Enums ------------------------------------------------------------------

class AccountType(str, enum.Enum):
    """Top-level account categorization.

    Debit-positive: ``asset``, ``expense``.
        Balance = SUM(debit) - SUM(credit).
    Credit-positive: ``liability``, ``equity``, ``revenue``.
        Balance = SUM(credit) - SUM(debit).

    Use ``AccountType.is_debit_positive`` to choose the formula.
    """

    asset = "asset"
    liability = "liability"
    equity = "equity"
    revenue = "revenue"
    expense = "expense"

    @property
    def is_debit_positive(self) -> bool:
        return self in (AccountType.asset, AccountType.expense)


# --- Money helper -----------------------------------------------------------

# Single source of truth for the money column type. Use throughout.
def money_column(**kwargs) -> "Mapped[Decimal]":
    return mapped_column(Numeric(14, 2), nullable=False, **kwargs)


# --- Account ----------------------------------------------------------------

class Account(Base, TimestampMixin, TenantScopedMixin):
    """A node in the Chart of Accounts.

    Codes follow a 4-digit numeric scheme (1000-5999) with hierarchical
    leading-digit semantics:
        1xxx = Assets, 2xxx = Liabilities, 3xxx = Equity,
        4xxx = Revenue, 5xxx = Expenses.

    Internal accounts the system needs to find by stable name (Cash, Sales
    Revenue, COGS, Inventory, Accounts Receivable, Owner's Drawings) carry a
    ``system_key`` so the sales/expense/treasury services can look them up
    without hardcoding UUIDs or account codes.
    """

    __tablename__ = "accounts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_accounts_tenant_code"),
        UniqueConstraint(
            "tenant_id", "system_key", name="uq_accounts_tenant_system_key"
        ),
        Index("ix_accounts_tenant_type", "tenant_id", "type"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()

    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    name_ar: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    type: Mapped[AccountType] = mapped_column(
        Enum(AccountType, name="account_type"), nullable=False
    )

    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=True,
    )
    parent: Mapped[Optional["Account"]] = relationship(
        "Account", remote_side="Account.id", lazy="select"
    )

    # Stable lookup key for system-managed accounts (cash, ar, ap, sales, ...).
    # Nullable: leaf accounts the user adds themselves have no system_key.
    system_key: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    is_active: Mapped[bool] = mapped_column(
        nullable=False, default=True, server_default="true"
    )

    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Account {self.code} {self.name} ({self.type.value})>"


# --- Journal Entry (header) --------------------------------------------------

class JournalEntry(Base, TimestampMixin, TenantScopedMixin):
    """One accounting event. Header row for a set of balanced ``JournalLine``s.

    Source modules pass a short ``source`` tag (``sale``, ``purchase``,
    ``expense``, ``capital``, ``manual``, ``reversal``) and an optional
    ``source_ref`` (e.g. ``sale:abc123-...``) so reports can group by origin.
    """

    __tablename__ = "journal_entries"
    __table_args__ = (
        Index("ix_journal_entries_tenant_date", "tenant_id", "entry_date"),
        Index("ix_journal_entries_source", "tenant_id", "source"),
        Index("ix_journal_entries_source_ref", "tenant_id", "source_ref"),
        Index("ix_journal_entries_branch", "branch_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()

    branch_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("branches.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    entry_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Short tag describing the origin (e.g. "sale", "purchase", "expense",
    # "capital", "manual", "reversal").
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="manual")

    # Free-form back-reference (e.g. "sale:<uuid>", "expense:<uuid>") so
    # downstream reports can hop back to the source row.
    source_ref: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    reference: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # ``posted_at`` is set at creation time in MVP (no draft state). When we
    # add drafts later, this becomes nullable until posted.
    posted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    posted_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Reversal linkage: filled on the *reversal* entry pointing at the
    # original. The original gets ``reversed_by_id`` populated.
    reverses_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("journal_entries.id", ondelete="RESTRICT"),
        nullable=True,
    )

    lines: Mapped[list["JournalLine"]] = relationship(
        "JournalLine",
        back_populates="entry",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<JournalEntry {self.entry_date} {self.source} ref={self.reference}>"


# --- Journal Line (detail) ---------------------------------------------------

class JournalLine(Base, TenantScopedMixin):
    """A single debit or credit row against an account.

    ``debit`` XOR ``credit`` > 0. Both >= 0. Enforced by CHECK constraint.

    Counterparty tagging
    --------------------
    For AR/AP lines (account.system_key in {AR, AP}) the line carries a
    ``customer_id`` or ``supplier_id`` so per-counterparty balances are
    queryable from the ledger itself — no secondary cache table needed,
    and the ledger is the single source of truth for financial state.

    For all other lines, both fields are NULL. The service that posts the
    line decides; no DB-level enforcement of "AR lines must have customer_id"
    because (a) reversals and adjustments may legitimately tag the
    counterparty as NULL, (b) a tenant might use the AR account for general
    receivables without a per-party split.
    """

    __tablename__ = "journal_lines"
    __table_args__ = (
        CheckConstraint("debit >= 0", name="ck_journal_lines_debit_nonneg"),
        CheckConstraint("credit >= 0", name="ck_journal_lines_credit_nonneg"),
        CheckConstraint(
            "(debit > 0 AND credit = 0) OR (debit = 0 AND credit > 0)",
            name="ck_journal_lines_debit_xor_credit",
        ),
        Index("ix_journal_lines_entry", "entry_id"),
        Index("ix_journal_lines_account", "account_id"),
        Index("ix_journal_lines_tenant_account", "tenant_id", "account_id"),
        Index("ix_journal_lines_customer", "tenant_id", "customer_id"),
        Index("ix_journal_lines_supplier", "tenant_id", "supplier_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()

    entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("journal_entries.id", ondelete="CASCADE"),
        nullable=False,
    )
    entry: Mapped["JournalEntry"] = relationship("JournalEntry", back_populates="lines")

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )

    debit: Mapped[Decimal] = money_column(default=Decimal("0"), server_default="0")
    credit: Mapped[Decimal] = money_column(default=Decimal("0"), server_default="0")

    # Optional counterparty tags. Set on AR lines (customer_id) and AP lines
    # (supplier_id) so per-counterparty balances roll up from the ledger
    # directly. Both NULL on lines that don't represent a receivable/payable.
    customer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=True,
    )
    supplier_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=True,
    )

    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        side = f"DR {self.debit}" if self.debit > 0 else f"CR {self.credit}"
        return f"<JournalLine acct={self.account_id} {side}>"
