"""Pydantic schemas for the auth module.

Request shapes are strict (``extra='forbid'``) so typos in the client surface
as 422s instead of silently being ignored. Response shapes are explicit so
the OpenAPI surface is predictable when we add Swagger in F16.
"""

from __future__ import annotations

import re
import uuid
from typing import Optional

from pydantic import EmailStr, Field, field_validator

from app.core.http.validation import BaseSchema


# --- Constraints ------------------------------------------------------------

_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_.\-]{3,32}$")
_TENANT_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{1,62}[a-z0-9]$")


def _validate_password_strength(value: str) -> str:
    """Minimum password rules. Tunable from a config dict later.

    Currently: ≥10 chars, mix of letters and digits. Tight enough to block
    "12345678" without forcing users into unmemorable passwords.
    """
    if len(value) < 10:
        raise ValueError("Password must be at least 10 characters")
    if not re.search(r"[A-Za-z]", value):
        raise ValueError("Password must contain a letter")
    if not re.search(r"\d", value):
        raise ValueError("Password must contain a digit")
    return value


# --- Requests --------------------------------------------------------------

class SignupRequest(BaseSchema):
    """Sign up a new tenant.

    Atomically creates: ``tenants`` row, default ``branches`` row, owner
    ``users`` row. The first user is the tenant owner and bypasses
    ``must_change_password``.
    """

    tenant_slug: str = Field(..., min_length=3, max_length=64)
    tenant_name: str = Field(..., min_length=2, max_length=200)

    owner_name: str = Field(..., min_length=2, max_length=200)
    owner_email: EmailStr
    owner_username: str = Field(..., min_length=3, max_length=64)
    owner_password: str = Field(..., min_length=10, max_length=128)

    # Optional: the default branch the signup flow creates.
    default_branch_name: str = Field(default="Main Branch", max_length=200)
    default_branch_code: str = Field(default="MAIN", max_length=20)

    @field_validator("tenant_slug")
    @classmethod
    def _slug(cls, v: str) -> str:
        v = v.lower().strip()
        if not _TENANT_SLUG_RE.match(v):
            raise ValueError(
                "tenant_slug must be 3-64 chars, lowercase letters, digits, or dashes; "
                "cannot start or end with a dash"
            )
        return v

    @field_validator("owner_username")
    @classmethod
    def _username(cls, v: str) -> str:
        if not _USERNAME_RE.match(v):
            raise ValueError(
                "username must be 3-32 chars, alphanumeric plus _ . -"
            )
        return v

    @field_validator("owner_password")
    @classmethod
    def _password(cls, v: str) -> str:
        return _validate_password_strength(v)


class LoginRequest(BaseSchema):
    """Username + password against a specific tenant.

    Tenant identification: either ``tenant_slug`` (preferred — comes from the
    URL the user opens, e.g. ``shop1.kingstore.app``) or omitted, in which
    case we look up the (tenant, user) pair by email which is globally unique
    within email + tenant context (less safe; will be tightened to require
    tenant_slug once the frontend lands).
    """

    tenant_slug: Optional[str] = None
    username: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1, max_length=128)


class RefreshRequest(BaseSchema):
    """Empty body — refresh token is read from the Authorization header.

    Kept as a class so the OpenAPI schema explicitly says "no body".
    """


class LogoutRequest(BaseSchema):
    """Empty body — current refresh JTI is read from token claims and revoked."""


class ChangePasswordRequest(BaseSchema):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=10, max_length=128)

    @field_validator("new_password")
    @classmethod
    def _new(cls, v: str) -> str:
        return _validate_password_strength(v)


# --- Responses --------------------------------------------------------------

class TokenPairResponse(BaseSchema):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int  # access TTL in seconds


class UserResponse(BaseSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    username: str
    email: str
    name: str
    role: str
    is_active: bool
    must_change_password: bool
    default_branch_id: Optional[uuid.UUID]


class TenantResponse(BaseSchema):
    id: uuid.UUID
    slug: str
    name: str
    status: str


class SignupResponse(BaseSchema):
    tenant: TenantResponse
    user: UserResponse
    tokens: TokenPairResponse


class LoginResponse(BaseSchema):
    user: UserResponse
    tokens: TokenPairResponse


class MeResponse(BaseSchema):
    user: UserResponse
    tenant: TenantResponse
    permissions: list[str]
