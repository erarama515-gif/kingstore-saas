"""Auth-related ORM models.

We persist refresh tokens server-side so logout/revocation are real (a JWT
on its own can't be invalidated). The access token stays stateless.

Storage scheme: we hash the JWT JTI before storing it, so a leaked DB dump
alone cannot replay sessions.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
)
from sqlalchemy.dialects.postgresql import INET, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import Base, TenantScopedMixin, TimestampMixin, uuid_pk


class RefreshToken(Base, TimestampMixin, TenantScopedMixin):
    """One row per issued refresh JWT.

    Lookup is by ``jti_hash`` (SHA-256 of the JTI claim), so a stolen DB
    snapshot does not reveal the live tokens. Rotation: on a successful
    refresh, the old row is marked ``revoked_at = now()`` and a new row is
    written. Reuse detection: if a *revoked* row's hash is presented, all
    of that user's tokens are nuked (potential theft).
    """

    __tablename__ = "refresh_tokens"
    __table_args__ = (
        Index("ix_refresh_tokens_user_id", "user_id"),
        Index("ix_refresh_tokens_jti_hash", "jti_hash", unique=True),
        Index("ix_refresh_tokens_expires_at", "expires_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # SHA-256 hex digest of the JWT JTI claim.
    jti_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Set when the token is revoked (logout, rotation, theft response).
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Token theft response: set when a previously-revoked token is replayed.
    # The row stays in the table for forensic visibility but the user's
    # active sessions are also nuked at that moment.
    is_compromised: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    # Audit metadata for the issuance event.
    ip_address: Mapped[Optional[str]] = mapped_column(INET, nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None and not self.is_compromised

    def __repr__(self) -> str:  # pragma: no cover
        return f"<RefreshToken user={self.user_id} active={self.is_active}>"
