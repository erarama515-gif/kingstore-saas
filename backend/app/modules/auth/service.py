"""Auth service — the only public surface of the auth module.

Other modules and routes import from here. Models and repository are
implementation details.

Flow contracts:

* ``signup``                creates tenant + default branch + owner user atomically
* ``login``                 verifies credentials, issues token pair, persists refresh
* ``refresh``               validates incoming refresh, rotates, persists new one
* ``logout``                revokes the presented refresh
* ``change_password``       requires current password, sets a new one, revokes sessions
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from flask import current_app, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_jwt,
    get_jwt_identity,
)
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import Conflict, Forbidden, Unauthorized

from app.core.security.hashing import hash_password, needs_rehash, verify_password
from app.extensions import db, redis_client
from app.modules.accounting.coa_seed import seed_default_chart
from app.modules.auth import repository as repo
from app.modules.auth.schemas import (
    LoginRequest,
    SignupRequest,
)
from app.modules.branches.models import Branch
from app.modules.rbac import permissions_for_role
from app.modules.tenants.models import Tenant, TenantStatus
from app.modules.users.models import User, UserRole


log = logging.getLogger(__name__)


# --- Brute-force lockout (Redis sliding-window) ----------------------------

_LOCKOUT_MAX_ATTEMPTS = 5
_LOCKOUT_WINDOW_SECONDS = 15 * 60       # 15 minutes
_LOCKOUT_KEY_FMT = "auth:lockout:{tenant}:{username}"


def _lockout_key(tenant_id: uuid.UUID | str, username: str) -> str:
    return _LOCKOUT_KEY_FMT.format(tenant=tenant_id, username=username.lower())


def _record_failed_attempt(tenant_id: uuid.UUID, username: str) -> int:
    if redis_client is None:
        return 0  # Redis unavailable: don't block logins on infra failure.
    key = _lockout_key(tenant_id, username)
    count = redis_client.incr(key)
    if count == 1:
        redis_client.expire(key, _LOCKOUT_WINDOW_SECONDS)
    return int(count)


def _clear_failed_attempts(tenant_id: uuid.UUID, username: str) -> None:
    if redis_client is None:
        return
    redis_client.delete(_lockout_key(tenant_id, username))


def _is_locked(tenant_id: uuid.UUID, username: str) -> bool:
    if redis_client is None:
        return False
    val = redis_client.get(_lockout_key(tenant_id, username))
    try:
        return val is not None and int(val) >= _LOCKOUT_MAX_ATTEMPTS
    except (TypeError, ValueError):
        return False


# --- Result containers ------------------------------------------------------

@dataclass(slots=True)
class TokenPair:
    access_token: str
    refresh_token: str
    expires_in: int


@dataclass(slots=True)
class AuthResult:
    user: User
    tenant: Tenant
    tokens: TokenPair


# --- Internal helpers -------------------------------------------------------

def _issue_pair(user: User, tenant: Tenant) -> TokenPair:
    """Create access + refresh tokens, persist refresh JTI hash."""
    perms = sorted(permissions_for_role(user.role))
    claims = {
        "tid": str(tenant.id),
        "bid": str(user.default_branch_id) if user.default_branch_id else None,
        "role": user.role.value,
        "perms": perms,
    }
    identity = str(user.id)
    access_token = create_access_token(identity=identity, additional_claims=claims)
    refresh_token = create_refresh_token(identity=identity, additional_claims=claims)

    # Decode the refresh we just minted to learn its JTI and exp claim.
    refresh_claims = decode_token(refresh_token)
    jti = refresh_claims["jti"]
    expires_at = datetime.fromtimestamp(refresh_claims["exp"], tz=timezone.utc)

    repo.store_refresh_token(
        db.session,
        tenant_id=tenant.id,
        user_id=user.id,
        jti=jti,
        expires_at=expires_at,
        ip_address=_client_ip(),
        user_agent=request.headers.get("User-Agent") if request else None,
    )

    access_ttl = int(current_app.config["JWT_ACCESS_TOKEN_EXPIRES"].total_seconds())
    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=access_ttl,
    )


def _client_ip() -> Optional[str]:
    if request is None:
        return None
    # nginx sets X-Forwarded-For; trust it because the app sits behind nginx.
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.remote_addr


# --- Public API -------------------------------------------------------------

def signup(payload: SignupRequest) -> AuthResult:
    """Atomically create tenant + default branch + owner + first token pair.

    Single transaction: if any step fails, nothing is persisted.

    Raises:
        Conflict: tenant_slug or owner_username/email collide with an
            existing row.
    """
    session = db.session

    # Pre-flight uniqueness check (the DB constraints would catch this too,
    # but a 409 with a useful message beats a generic IntegrityError).
    if repo.tenant_slug_exists(session, payload.tenant_slug):
        raise Conflict("Tenant slug already taken.")

    tenant = Tenant(
        slug=payload.tenant_slug,
        name=payload.tenant_name,
        status=TenantStatus.trial,
    )
    session.add(tenant)
    session.flush()  # need tenant.id for the branch and user FKs

    branch = Branch(
        tenant_id=tenant.id,
        name=payload.default_branch_name,
        code=payload.default_branch_code.upper(),
    )
    session.add(branch)
    session.flush()

    tenant.default_branch_id = branch.id

    user = User(
        tenant_id=tenant.id,
        username=payload.owner_username.lower(),
        email=payload.owner_email.lower(),
        password_hash=hash_password(payload.owner_password),
        name=payload.owner_name,
        role=UserRole.owner,
        is_active=True,
        must_change_password=False,
        default_branch_id=branch.id,
        password_changed_at=datetime.now(timezone.utc),
    )
    session.add(user)

    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        # The pre-flight covered slug; username/email collisions land here.
        raise Conflict("Username or email already taken.") from exc

    # Seed the Chart of Accounts so downstream modules can post journals
    # immediately. Part of the same transaction — if it fails, the whole
    # signup rolls back.
    seed_default_chart(session, tenant.id)

    tokens = _issue_pair(user, tenant)
    user.last_login_at = datetime.now(timezone.utc)

    session.commit()
    log.info("tenant_signup", extra={"tenant_id": str(tenant.id), "user_id": str(user.id)})
    return AuthResult(user=user, tenant=tenant, tokens=tokens)


def login(payload: LoginRequest) -> AuthResult:
    """Verify credentials and issue tokens.

    Raises:
        Unauthorized: bad credentials, inactive user, missing tenant.
        Forbidden: tenant is suspended/canceled, or account locked out.
    """
    session = db.session

    tenant: Optional[Tenant] = None
    if payload.tenant_slug:
        tenant = repo.get_tenant_by_slug(session, payload.tenant_slug)
        if tenant is None:
            # Generic message — don't leak which tenant slugs exist.
            raise Unauthorized("Invalid credentials.")

    # Lockout check (per tenant + username)
    if tenant and _is_locked(tenant.id, payload.username):
        raise Forbidden("Too many failed attempts. Try again in a few minutes.")

    # Username can be a username or email. Try both.
    user: Optional[User] = None
    if tenant:
        user = repo.get_user_by_username(
            session, tenant_id=tenant.id, username=payload.username.lower()
        )
        if user is None:
            user = repo.get_user_by_email(
                session, tenant_id=tenant.id, email=payload.username.lower()
            )
    else:
        # No tenant_slug given: we need one. The frontend should always send
        # it. Reject explicitly so flows can't accidentally cross tenants.
        raise Unauthorized("Tenant required.")

    if user is None or not verify_password(payload.password, user.password_hash):
        if tenant is not None:
            _record_failed_attempt(tenant.id, payload.username)
        raise Unauthorized("Invalid credentials.")

    if not user.is_active:
        raise Forbidden("Account is disabled.")

    if tenant.status in (TenantStatus.suspended, TenantStatus.canceled):
        raise Forbidden(f"Tenant is {tenant.status.value}.")

    # Upgrade hash if argon2 params have rolled forward
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)

    _clear_failed_attempts(tenant.id, payload.username)

    tokens = _issue_pair(user, tenant)
    user.last_login_at = datetime.now(timezone.utc)
    session.commit()

    log.info("login_success", extra={"user_id": str(user.id), "tenant_id": str(tenant.id)})
    return AuthResult(user=user, tenant=tenant, tokens=tokens)


def refresh() -> AuthResult:
    """Rotate the presented refresh token.

    Must be called from inside a ``@jwt_required(refresh=True)`` route so
    ``get_jwt()`` / ``get_jwt_identity()`` are populated.

    Raises:
        Unauthorized: token unknown, expired, or theft detected.
    """
    session = db.session
    claims = get_jwt()
    user_id = get_jwt_identity()
    jti = claims.get("jti")
    if not user_id or not jti:
        raise Unauthorized("Invalid refresh token.")

    row = repo.get_refresh_by_jti(session, jti)
    if row is None:
        # Token we never issued. Either tampered or already pruned. Treat as
        # a *potential* theft but be conservative — only nuke if the user id
        # in the claim is real.
        raise Unauthorized("Invalid refresh token.")

    # --- Theft detection -----------------------------------------------------
    if row.revoked_at is not None or row.is_compromised:
        # A revoked token was presented again. Nuke all of this user's
        # active sessions and require re-login from scratch.
        nuked = repo.mark_compromised_and_revoke_all(session, row.user_id)
        session.commit()
        log.warning(
            "refresh_token_reuse_detected",
            extra={"user_id": str(row.user_id), "nuked_sessions": nuked},
        )
        raise Unauthorized("Refresh token reuse detected. Please log in again.")

    if row.expires_at <= datetime.now(timezone.utc):
        repo.revoke_token(session, row)
        session.commit()
        raise Unauthorized("Refresh token expired.")

    user = repo.get_user_by_id(session, row.user_id)
    if user is None or not user.is_active:
        repo.revoke_token(session, row)
        session.commit()
        raise Unauthorized("Account unavailable.")

    tenant = session.get(Tenant, user.tenant_id)
    if tenant is None or tenant.status in (TenantStatus.suspended, TenantStatus.canceled):
        repo.revoke_token(session, row)
        session.commit()
        raise Forbidden("Tenant unavailable.")

    # Rotate
    repo.revoke_token(session, row)
    tokens = _issue_pair(user, tenant)
    session.commit()
    return AuthResult(user=user, tenant=tenant, tokens=tokens)


def logout() -> None:
    """Revoke the presented refresh token. No-op if it's already revoked."""
    session = db.session
    claims = get_jwt()
    jti = claims.get("jti")
    if not jti:
        return
    row = repo.get_refresh_by_jti(session, jti)
    if row is not None:
        repo.revoke_token(session, row)
        session.commit()


def change_password(*, user_id: uuid.UUID, current_pwd: str, new_pwd: str) -> None:
    """Verify current password, set new one, revoke all sessions."""
    session = db.session
    user = repo.get_user_by_id(session, user_id)
    if user is None:
        raise Unauthorized("User not found.")
    if not verify_password(current_pwd, user.password_hash):
        raise Unauthorized("Current password is incorrect.")
    user.password_hash = hash_password(new_pwd)
    user.password_changed_at = datetime.now(timezone.utc)
    user.must_change_password = False
    repo.mark_compromised_and_revoke_all(session, user.id)
    session.commit()
    log.info("password_changed", extra={"user_id": str(user.id)})


def is_jti_revoked(jti: str) -> bool:
    """JWT blocklist callback. Returns True to reject the token."""
    if not jti:
        return False
    row = repo.get_refresh_by_jti(db.session, jti)
    # We only persist refresh JTIs. For access tokens (which we don't
    # persist), the JTI won't match a row, and we let them through — they're
    # short-lived. Refresh tokens are revoked iff the row says so.
    if row is None:
        return False
    return row.revoked_at is not None or row.is_compromised
