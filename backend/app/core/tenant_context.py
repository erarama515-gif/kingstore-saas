"""Per-request tenant context.

On every request, *if* a valid JWT is presented, populate ``g.user_id``,
``g.tenant_id``, ``g.branch_id``, ``g.role``, ``g.perms`` from the token's
claims. The tenant-scope SQLAlchemy event listener (installed in
``app.core.db.base``) then automatically filters every SELECT by
``g.tenant_id``.

Routes that *require* authentication declare it via ``@jwt_required()`` (from
flask-jwt-extended) and/or ``@require_perm(...)`` (from
``app.core.permissions``). This hook is non-blocking on purpose — it does not
reject requests without a token; that's the route decorator's job.
"""

from __future__ import annotations

import uuid
from typing import Optional

from flask import Flask, g, request
from flask_jwt_extended import get_jwt, verify_jwt_in_request
from flask_jwt_extended.exceptions import NoAuthorizationError
from jwt.exceptions import PyJWTError

from app.core.db.base import install_tenant_scope


_PUBLIC_PREFIXES = (
    "/api/v1/health",
    "/api/v1/ready",
    "/api/v1/auth/login",
    "/api/v1/auth/signup",
    # /auth/refresh, /auth/logout, /auth/me, /auth/change-password all require
    # auth — handled by @jwt_required decorators on the routes themselves.
)


def register_tenant_hooks(app: Flask) -> None:
    """Install the request hook + the SA tenant-filter event listener."""
    install_tenant_scope(None)

    @app.before_request
    def _populate_context() -> None:
        # Reset every request so g doesn't leak between unrelated requests.
        g.user_id = None
        g.tenant_id = None
        g.branch_id = None
        g.role = None
        g.perms = []

        path = request.path or ""
        if any(path.startswith(p) for p in _PUBLIC_PREFIXES):
            return

        # Try to decode an optional JWT. Routes that require auth will enforce
        # presence themselves via @jwt_required.
        try:
            verify_jwt_in_request(optional=True)
        except (NoAuthorizationError, PyJWTError):
            return

        claims = get_jwt() or {}
        if not claims:
            return

        sub = claims.get("sub")
        tid = claims.get("tid")
        bid = claims.get("bid")
        try:
            g.user_id = uuid.UUID(sub) if sub else None
            g.tenant_id = uuid.UUID(tid) if tid else None
            g.branch_id = uuid.UUID(bid) if bid else None
        except (TypeError, ValueError):
            # Malformed claims: leave context cleared. @jwt_required will 401.
            g.user_id = None
            g.tenant_id = None
            g.branch_id = None
            return

        g.role = claims.get("role")
        g.perms = list(claims.get("perms") or [])


def current_user_id() -> Optional[uuid.UUID]:
    return getattr(g, "user_id", None)


def current_tenant_id() -> Optional[uuid.UUID]:
    return getattr(g, "tenant_id", None)


def current_branch_id() -> Optional[uuid.UUID]:
    return getattr(g, "branch_id", None)


def current_permissions() -> list[str]:
    return list(getattr(g, "perms", []) or [])
