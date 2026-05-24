"""SQLAlchemy 2.x declarative base, mixins, and tenant scoping.

Design notes
============

* All models inherit from ``Base``. Tenant-scoped business tables additionally
  inherit ``TenantScopedMixin``; that mixin contributes a ``tenant_id`` column
  and opts the model in to automatic ``WHERE tenant_id = <current>`` filtering.
* Tenant scoping is enforced via a SQLAlchemy ORM event (``do_orm_execute``)
  using ``with_loader_criteria``. This intercepts every SELECT — including
  relationship loading — and appends the predicate. Repositories never have to
  remember to filter manually. See ``install_tenant_scope``.
* INSERT/UPDATE/DELETE protection happens at the service layer (and as a
  defense-in-depth net via Postgres RLS in ``infra/postgres/init.sql``).
* Naming convention is set on the ``MetaData`` so Alembic generates predictable,
  diff-friendly constraint names instead of random anonymous ones.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from flask import g, has_app_context
from sqlalchemy import DateTime, ForeignKey, MetaData, event, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    declared_attr,
    mapped_column,
    with_loader_criteria,
)


# --- Naming convention (Alembic-friendly) -----------------------------------

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Project-wide declarative base."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


# --- Common typed helpers ---------------------------------------------------

def uuid_pk() -> Mapped[uuid.UUID]:
    """Standard UUID primary key column."""
    return mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- Mixins ------------------------------------------------------------------

class TimestampMixin:
    """``created_at`` / ``updated_at`` columns. Server-side defaults so direct
    SQL inserts (e.g. ETL) also get values."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
        onupdate=_utcnow,
    )


class SoftDeleteMixin:
    """``deleted_at`` column for soft delete.

    Filtering deleted rows by default is *not* done here — that's the
    repository's job, because some flows (e.g. audit, reporting) legitimately
    need to read tombstoned rows.
    """

    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


class TenantScopedMixin:
    """Marks a model as belonging to a tenant.

    Tables that inherit this mixin get a non-nullable ``tenant_id`` UUID FK
    and are automatically tenant-filtered on read via the SA event installed
    by :func:`install_tenant_scope`.
    """

    # The FK target is declared as a string to avoid an import cycle with
    # ``app.modules.tenants.models``.
    @declared_attr
    @classmethod
    def tenant_id(cls) -> Mapped[uuid.UUID]:
        return mapped_column(
            UUID(as_uuid=True),
            ForeignKey("tenants.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        )


# --- Automatic tenant filtering --------------------------------------------

def _current_tenant_id() -> Optional[uuid.UUID]:
    """Return the tenant_id bound to this request, or None outside requests."""
    if not has_app_context():
        return None
    return getattr(g, "tenant_id", None)


def install_tenant_scope(engine_or_session: Any) -> None:
    """Install the global tenant-filtering ORM event.

    Called once at app init (from ``register_tenant_hooks``). Listens for
    SELECT execution and injects a ``WHERE tenant_id = :tid`` clause for every
    ``TenantScopedMixin`` subclass referenced in the query — *only when* a
    tenant is bound to the request context. Outside a request (e.g. migrations,
    seed scripts), no filter is applied so admin tooling still works.

    The ``include_aliases=True`` flag ensures joined / aliased instances are
    also covered.
    """

    @event.listens_for(Session, "do_orm_execute")
    def _add_tenant_filter(execute_state: Any) -> None:  # pragma: no cover - SA hook
        if not execute_state.is_select:
            return
        # Allow explicit bypass for admin/tooling queries.
        if execute_state.execution_options.get("skip_tenant_filter"):
            return
        tid = _current_tenant_id()
        if tid is None:
            return
        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(
                TenantScopedMixin,
                lambda cls: cls.tenant_id == tid,
                include_aliases=True,
            )
        )
