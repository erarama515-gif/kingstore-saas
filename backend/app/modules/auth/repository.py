"""Auth-related data access.

Repositories never apply business rules — they read/write the DB and return
ORM objects. All cross-table or cross-tenant logic lives in ``service.py``.

Note on tenant scoping: most queries here run *before* a request has a
tenant context (login, signup). That means the global tenant filter
(``with_loader_criteria``) is inactive — its hook checks ``g.tenant_id``
which is None during these flows. We still filter explicitly by tenant
when needed so the behavior is the same regardless.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.auth.models import RefreshToken
from app.modules.branches.models import Branch
from app.modules.tenants.models import Tenant
from app.modules.users.models import User


# --- Helpers ----------------------------------------------------------------

def hash_jti(jti: str) -> str:
    """SHA-256 of a JWT JTI claim, hex-encoded. Used as the row key."""
    return hashlib.sha256(jti.encode("utf-8")).hexdigest()


# --- Tenants ----------------------------------------------------------------

def get_tenant_by_slug(session: Session, slug: str) -> Optional[Tenant]:
    return session.execute(
        select(Tenant)
        .where(Tenant.slug == slug.lower())
        .execution_options(skip_tenant_filter=True)
    ).scalar_one_or_none()


def tenant_slug_exists(session: Session, slug: str) -> bool:
    return get_tenant_by_slug(session, slug) is not None


# --- Users ------------------------------------------------------------------

def get_user_by_username(
    session: Session, *, tenant_id: uuid.UUID, username: str
) -> Optional[User]:
    return session.execute(
        select(User)
        .where(User.tenant_id == tenant_id, User.username == username)
        .execution_options(skip_tenant_filter=True)
    ).scalar_one_or_none()


def get_user_by_email(
    session: Session, *, tenant_id: uuid.UUID, email: str
) -> Optional[User]:
    return session.execute(
        select(User)
        .where(User.tenant_id == tenant_id, User.email == email.lower())
        .execution_options(skip_tenant_filter=True)
    ).scalar_one_or_none()


def get_user_by_id(session: Session, user_id: uuid.UUID) -> Optional[User]:
    return session.execute(
        select(User).where(User.id == user_id)
        .execution_options(skip_tenant_filter=True)
    ).scalar_one_or_none()


# --- Branches ---------------------------------------------------------------

def get_branch(session: Session, branch_id: uuid.UUID) -> Optional[Branch]:
    return session.execute(
        select(Branch).where(Branch.id == branch_id)
        .execution_options(skip_tenant_filter=True)
    ).scalar_one_or_none()


# --- Refresh tokens ---------------------------------------------------------

def store_refresh_token(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    jti: str,
    expires_at: datetime,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> RefreshToken:
    rt = RefreshToken(
        tenant_id=tenant_id,
        user_id=user_id,
        jti_hash=hash_jti(jti),
        expires_at=expires_at,
        ip_address=ip_address,
        user_agent=(user_agent or "")[:500] or None,
    )
    session.add(rt)
    session.flush()
    return rt


def get_refresh_by_jti(session: Session, jti: str) -> Optional[RefreshToken]:
    return session.execute(
        select(RefreshToken)
        .where(RefreshToken.jti_hash == hash_jti(jti))
        .execution_options(skip_tenant_filter=True)
    ).scalar_one_or_none()


def revoke_token(session: Session, rt: RefreshToken) -> None:
    if rt.revoked_at is None:
        rt.revoked_at = datetime.now(timezone.utc)


def mark_compromised_and_revoke_all(session: Session, user_id: uuid.UUID) -> int:
    """Theft response: nuke every active refresh token for a user.

    Called when a previously-revoked token is replayed — strong signal that
    the refresh token was stolen.
    """
    rows = session.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
        .execution_options(skip_tenant_filter=True)
    ).scalars().all()
    now = datetime.now(timezone.utc)
    for r in rows:
        r.revoked_at = now
        r.is_compromised = True
    return len(rows)
