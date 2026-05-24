"""Static permission catalog.

Naming: ``<module>.<verb>`` where verb is one of
``read | create | update | delete | manage`` (manage = full control).
Specialized actions get explicit verbs (``sales.refund``, ``treasury.close_day``).

Roles inherit from each other implicitly via union: owner gets everything,
admin gets everything except billing/destroy-tenant, etc.

When you add a permission code: also add it to the appropriate role's set
below. The migration that seeds ``role_permissions`` reads from
``PERMISSIONS_BY_ROLE`` so DB stays in sync with code.
"""

from __future__ import annotations

from typing import Final

from app.modules.users.models import UserRole


# --- The catalog ------------------------------------------------------------

class Permission:
    """Namespaced permission codes. Treat as constants."""

    # Tenant-level (owner only)
    TENANT_MANAGE = "tenants.manage"
    TENANT_DELETE = "tenants.delete"
    BILLING_READ = "billing.read"
    BILLING_MANAGE = "billing.manage"

    # Users & branches
    USERS_READ = "users.read"
    USERS_INVITE = "users.invite"
    USERS_UPDATE = "users.update"
    USERS_DEACTIVATE = "users.deactivate"
    BRANCHES_READ = "branches.read"
    BRANCHES_MANAGE = "branches.manage"

    # Products & inventory
    PRODUCTS_READ = "products.read"
    PRODUCTS_CREATE = "products.create"
    PRODUCTS_UPDATE = "products.update"
    PRODUCTS_DELETE = "products.delete"
    INVENTORY_READ = "inventory.read"
    INVENTORY_ADJUST = "inventory.adjust"
    INVENTORY_TRANSFER = "inventory.transfer"

    # Sales / POS
    SALES_READ = "sales.read"
    SALES_CREATE = "sales.create"
    SALES_REFUND = "sales.refund"
    SALES_VOID = "sales.void"
    DEBTS_READ = "debts.read"
    DEBTS_COLLECT = "debts.collect"

    # Customers / suppliers
    CUSTOMERS_READ = "customers.read"
    CUSTOMERS_MANAGE = "customers.manage"
    SUPPLIERS_READ = "suppliers.read"
    SUPPLIERS_MANAGE = "suppliers.manage"

    # Purchases
    PURCHASES_READ = "purchases.read"
    PURCHASES_CREATE = "purchases.create"

    # Repairs
    REPAIRS_READ = "repairs.read"
    REPAIRS_CREATE = "repairs.create"
    REPAIRS_UPDATE = "repairs.update"
    REPAIRS_DELIVER = "repairs.deliver"

    # Expenses & treasury
    EXPENSES_READ = "expenses.read"
    EXPENSES_CREATE = "expenses.create"
    TREASURY_READ = "treasury.read"
    TREASURY_CLOSE_DAY = "treasury.close_day"
    CAPITAL_READ = "capital.read"
    CAPITAL_MANAGE = "capital.manage"

    # Accounting
    ACCOUNTING_READ = "accounting.read"
    ACCOUNTING_POST = "accounting.post"  # post manual journal entries

    # Reports
    REPORTS_SALES = "reports.sales"
    REPORTS_INVENTORY = "reports.inventory"
    REPORTS_FINANCIAL = "reports.financial"  # P&L, BS, trial balance

    # Audit
    AUDIT_READ = "audit.read"


ALL_PERMISSIONS: Final[frozenset[str]] = frozenset(
    v for k, v in vars(Permission).items()
    if not k.startswith("_") and isinstance(v, str)
)


# --- Role → permission set ---------------------------------------------------

# Cashier: front-of-store. Can sell, collect debts, read inventory, take in
# repairs (but not deliver = recognize revenue).
_CASHIER = frozenset({
    Permission.PRODUCTS_READ,
    Permission.INVENTORY_READ,
    Permission.SALES_READ, Permission.SALES_CREATE,
    Permission.DEBTS_READ, Permission.DEBTS_COLLECT,
    Permission.CUSTOMERS_READ, Permission.CUSTOMERS_MANAGE,
    Permission.REPAIRS_READ, Permission.REPAIRS_CREATE,
    Permission.TREASURY_READ,
})

# Technician: repairs lifecycle only.
_TECHNICIAN = frozenset({
    Permission.PRODUCTS_READ, Permission.INVENTORY_READ,
    Permission.REPAIRS_READ, Permission.REPAIRS_CREATE,
    Permission.REPAIRS_UPDATE, Permission.REPAIRS_DELIVER,
    Permission.CUSTOMERS_READ,
})

# Warehouse manager: products + inventory + purchases.
_WAREHOUSE = frozenset({
    Permission.PRODUCTS_READ, Permission.PRODUCTS_CREATE,
    Permission.PRODUCTS_UPDATE,
    Permission.INVENTORY_READ, Permission.INVENTORY_ADJUST,
    Permission.INVENTORY_TRANSFER,
    Permission.SUPPLIERS_READ, Permission.SUPPLIERS_MANAGE,
    Permission.PURCHASES_READ, Permission.PURCHASES_CREATE,
    Permission.REPORTS_INVENTORY,
})

# Accountant: read everything financial, post journals, close day, run reports.
# No POS or product create.
_ACCOUNTANT = frozenset({
    Permission.PRODUCTS_READ,
    Permission.INVENTORY_READ,
    Permission.SALES_READ, Permission.SALES_REFUND, Permission.SALES_VOID,
    Permission.DEBTS_READ, Permission.DEBTS_COLLECT,
    Permission.CUSTOMERS_READ,
    Permission.SUPPLIERS_READ,
    Permission.PURCHASES_READ,
    Permission.REPAIRS_READ,
    Permission.EXPENSES_READ, Permission.EXPENSES_CREATE,
    Permission.TREASURY_READ, Permission.TREASURY_CLOSE_DAY,
    Permission.CAPITAL_READ, Permission.CAPITAL_MANAGE,
    Permission.ACCOUNTING_READ, Permission.ACCOUNTING_POST,
    Permission.REPORTS_SALES, Permission.REPORTS_INVENTORY, Permission.REPORTS_FINANCIAL,
    Permission.AUDIT_READ,
})

# Admin: all operational perms. Cannot delete the tenant or manage billing.
_ADMIN = ALL_PERMISSIONS - frozenset({
    Permission.TENANT_DELETE,
    Permission.BILLING_MANAGE,
})

# Owner: everything.
_OWNER = ALL_PERMISSIONS

# Viewer: read-only across the board.
_VIEWER = frozenset(p for p in ALL_PERMISSIONS if p.endswith(".read"))


PERMISSIONS_BY_ROLE: Final[dict[UserRole, frozenset[str]]] = {
    UserRole.owner: _OWNER,
    UserRole.admin: _ADMIN,
    UserRole.accountant: _ACCOUNTANT,
    UserRole.cashier: _CASHIER,
    UserRole.technician: _TECHNICIAN,
    UserRole.warehouse_manager: _WAREHOUSE,
    UserRole.viewer: _VIEWER,
}


def permissions_for_role(role: UserRole) -> frozenset[str]:
    """Return the (immutable) default permission set for ``role``."""
    return PERMISSIONS_BY_ROLE.get(role, frozenset())
