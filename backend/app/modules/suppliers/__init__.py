"""Suppliers module.

Master data for vendors. Mirrors the customers module but the accounting
direction is reversed: the system *owes* the supplier money (AP), so the
opening balance and ongoing posting flip sides.

Public surface mirrors customers: ``service.create_supplier``,
``supplier_balance`` (live from ledger), ``supplier_statement``.
"""

from app.modules.suppliers.service import (
    create_supplier,
    update_supplier,
    delete_supplier,
    get_supplier,
    list_suppliers,
    quick_lookup,
    supplier_balance,
    supplier_statement,
)


__all__ = [
    "create_supplier",
    "update_supplier",
    "delete_supplier",
    "get_supplier",
    "list_suppliers",
    "quick_lookup",
    "supplier_balance",
    "supplier_statement",
]
