"""JWT helpers.

We rely on ``flask-jwt-extended`` for the bulk of the work (token decode,
``@jwt_required``, blocklist hooks). This module adds:

* ``issue_token_pair(user, ...)`` — convenience for the auth module
* Claim shape contract: ``sub``, ``tid``, ``bid``, ``role``, ``perms``
* Hook registration for blocklist checks (refresh-token revocation table)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from flask_jwt_extended import create_access_token, create_refresh_token


def build_claims(
    *,
    tenant_id: uuid.UUID,
    branch_id: Optional[uuid.UUID],
    role: str,
    permissions: Iterable[str],
) -> dict[str, Any]:
    """Build the additional-claims dict added to both access and refresh tokens.

    The ``sub`` claim (subject = user id) is set separately by flask-jwt-extended
    via the ``identity=`` argument.
    """
    return {
        "tid": str(tenant_id),
        "bid": str(branch_id) if branch_id else None,
        "role": role,
        "perms": list(permissions),
        "iat": int(datetime.now(timezone.utc).timestamp()),
    }


def issue_token_pair(
    *,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    branch_id: Optional[uuid.UUID],
    role: str,
    permissions: Iterable[str],
) -> dict[str, str]:
    """Issue an (access, refresh) token pair with shared claims.

    The auth module is responsible for *persisting* the refresh token's ``jti``
    in the ``refresh_tokens`` table so it can be revoked.
    """
    claims = build_claims(
        tenant_id=tenant_id,
        branch_id=branch_id,
        role=role,
        permissions=permissions,
    )
    identity = str(user_id)
    return {
        "access_token": create_access_token(identity=identity, additional_claims=claims),
        "refresh_token": create_refresh_token(identity=identity, additional_claims=claims),
        "token_type": "Bearer",
    }
