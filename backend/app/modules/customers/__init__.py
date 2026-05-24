"""Customers module.

Stores customer master data and exposes the AR-aware service surface used
by the POS (quick lookup), sales (debt tracking), and reports (statements,
aging).

The accounting ledger is the financial source of truth for what each
customer owes; the cached fields on the Customer row are convenience
denormalizations the sales/payment services maintain. Reading
``service.customer_balance`` always recomputes from the journal so the
displayed number cannot drift out of sync.
"""

from app.modules.customers.service import (
    create_customer,
    update_customer,
    delete_customer,
    get_customer,
    list_customers,
    quick_lookup,
    customer_balance,
    customer_statement,
)


__all__ = [
    "create_customer",
    "update_customer",
    "delete_customer",
    "get_customer",
    "list_customers",
    "quick_lookup",
    "customer_balance",
    "customer_statement",
]
