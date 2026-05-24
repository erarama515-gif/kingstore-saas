"""Auth HTTP routes.

* ``POST /auth/signup``           public  — create tenant + owner
* ``POST /auth/login``            public  — exchange creds for tokens
* ``POST /auth/refresh``          refresh — rotate refresh, issue new pair
* ``POST /auth/logout``           access  — revoke current refresh
* ``GET  /auth/me``               access  — current user + tenant + perms
* ``POST /auth/change-password``  access  — change password, revoke sessions

Rate limits applied per-route. The brute-force lockout inside the service
adds a second layer for login specifically.
"""

from __future__ import annotations

import uuid

from flask import Blueprint
from flask_jwt_extended import get_jwt_identity, jwt_required
from werkzeug.exceptions import Unauthorized

from app.core.http.responses import created, no_content, ok
from app.core.http.validation import parse_json
from app.extensions import db, limiter
from app.modules.auth import service
from app.modules.auth.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    MeResponse,
    SignupRequest,
    SignupResponse,
    TenantResponse,
    TokenPairResponse,
    UserResponse,
)
from app.modules.rbac import permissions_for_role
from app.modules.tenants.models import Tenant
from app.modules.users.models import User, UserRole


auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


# --- Serializers (ORM → response schema) -----------------------------------

def _user_payload(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        tenant_id=user.tenant_id,
        username=user.username,
        email=user.email,
        name=user.name,
        role=user.role.value,
        is_active=user.is_active,
        must_change_password=user.must_change_password,
        default_branch_id=user.default_branch_id,
    )


def _tenant_payload(tenant: Tenant) -> TenantResponse:
    return TenantResponse(
        id=tenant.id,
        slug=tenant.slug,
        name=tenant.name,
        status=tenant.status.value,
    )


def _tokens_payload(result: service.AuthResult) -> TokenPairResponse:
    return TokenPairResponse(
        access_token=result.tokens.access_token,
        refresh_token=result.tokens.refresh_token,
        expires_in=result.tokens.expires_in,
    )


# --- Routes ----------------------------------------------------------------

@auth_bp.post("/signup")
@limiter.limit("10 per hour")
def signup_route():
    payload = parse_json(SignupRequest)
    result = service.signup(payload)
    body = SignupResponse(
        tenant=_tenant_payload(result.tenant),
        user=_user_payload(result.user),
        tokens=_tokens_payload(result),
    )
    return created(body.model_dump(mode="json"))


@auth_bp.post("/login")
@limiter.limit("30 per minute")
def login_route():
    payload = parse_json(LoginRequest)
    result = service.login(payload)
    body = LoginResponse(
        user=_user_payload(result.user),
        tokens=_tokens_payload(result),
    )
    return ok(body.model_dump(mode="json"))


@auth_bp.post("/refresh")
@jwt_required(refresh=True)
@limiter.limit("60 per minute")
def refresh_route():
    result = service.refresh()
    body = LoginResponse(
        user=_user_payload(result.user),
        tokens=_tokens_payload(result),
    )
    return ok(body.model_dump(mode="json"))


@auth_bp.post("/logout")
@jwt_required(refresh=True)
def logout_route():
    service.logout()
    return no_content()


@auth_bp.get("/me")
@jwt_required()
def me_route():
    user_id = get_jwt_identity()
    user = db.session.get(User, uuid.UUID(user_id))
    if user is None or not user.is_active:
        raise Unauthorized("User not available.")
    tenant = db.session.get(Tenant, user.tenant_id)
    perms = sorted(permissions_for_role(user.role))
    body = MeResponse(
        user=_user_payload(user),
        tenant=_tenant_payload(tenant),
        permissions=perms,
    )
    return ok(body.model_dump(mode="json"))


@auth_bp.post("/change-password")
@jwt_required()
@limiter.limit("10 per hour")
def change_password_route():
    payload = parse_json(ChangePasswordRequest)
    user_id = get_jwt_identity()
    service.change_password(
        user_id=uuid.UUID(user_id),
        current_pwd=payload.current_password,
        new_pwd=payload.new_password,
    )
    return no_content()
