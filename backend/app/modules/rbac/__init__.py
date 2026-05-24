"""RBAC — permission catalog and role-to-permission mapping.

This module is a *pure data* module: no routes, no services. It defines the
authoritative list of permission codes used by ``@require_perm(...)``
decorators and the default permission set granted to each role.

A future ``permissions`` table will allow tenant-level overrides (e.g. a
tenant can revoke a permission from the Cashier role for their own
installation). Until then, the static catalog is the source of truth.
"""

from app.modules.rbac.catalog import (
    ALL_PERMISSIONS,
    PERMISSIONS_BY_ROLE,
    Permission,
    permissions_for_role,
)


__all__ = [
    "Permission",
    "ALL_PERMISSIONS",
    "PERMISSIONS_BY_ROLE",
    "permissions_for_role",
]
