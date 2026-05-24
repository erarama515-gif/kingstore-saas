"""RBAC permission decorators.

Permission codes follow ``<module>.<action>`` convention:

    sales.create, sales.read, sales.refund
    inventory.adjust, products.update
    reports.financial.read
    users.invite, tenants.manage_billing

The actual permission *catalog* and role → permission mappings live in the
``users`` module (Phase F2). This file only provides the runtime check.
"""

from __future__ import annotations

from functools import wraps
from typing import Callable, Iterable, ParamSpec, TypeVar

from flask import abort
from flask_jwt_extended import jwt_required

from app.core.tenant_context import current_permissions


P = ParamSpec("P")
R = TypeVar("R")


def require_perm(*codes: str, require_all: bool = False) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator: require the caller to hold one (or all) of the given perms.

    Applies ``@jwt_required()`` implicitly so route authors only need one
    decorator. Returns 403 if the JWT is valid but the user lacks the perm,
    401 if no valid token is present (raised by ``@jwt_required``).
    """

    def decorator(fn: Callable[P, R]) -> Callable[P, R]:
        @jwt_required()
        @wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            held = set(current_permissions())
            wanted = set(codes)
            ok = (held >= wanted) if require_all else bool(held & wanted)
            if not ok:
                abort(403, description=f"Missing permission(s): {sorted(wanted - held)}")
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def has_perm(*codes: str, require_all: bool = False) -> bool:
    """Imperative check usable inside service code."""
    held = set(current_permissions())
    wanted = set(codes)
    return (held >= wanted) if require_all else bool(held & wanted)


def assert_perm(*codes: str, require_all: bool = False) -> None:
    if not has_perm(*codes, require_all=require_all):
        abort(403, description=f"Missing permission(s): {list(codes)}")


def require_role(*roles: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator gating on role name (Owner/Admin/Accountant/Cashier/...)."""

    def decorator(fn: Callable[P, R]) -> Callable[P, R]:
        @jwt_required()
        @wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            from flask import g
            if (getattr(g, "role", None) or "") not in set(roles):
                abort(403, description=f"Role not permitted: required one of {sorted(set(roles))}")
            return fn(*args, **kwargs)

        return wrapper

    return decorator


# Re-export for ergonomics
__all__ = ["require_perm", "require_role", "has_perm", "assert_perm"]


def _ignored(_perms: Iterable[str]) -> None:  # pragma: no cover - reserved
    """Reserved hook for future perm-catalog validation."""
    return None
