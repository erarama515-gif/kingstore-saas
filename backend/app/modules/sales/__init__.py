"""Sales / POS module.

The headline customer-facing feature: ring up a sale, accept cash or credit,
print a receipt. The service composes inventory.decrement_for_sale (which
posts DR COGS / CR Inventory) with the revenue side (DR Cash-or-AR / CR
Sales-or-Service Revenue) in a single transaction.
"""

from app.modules.sales.service import (
    create_sale,
    refund_sale,
    apply_payment,
    get_sale,
    list_sales,
    list_open_debts,
)


__all__ = [
    "create_sale",
    "refund_sale",
    "apply_payment",
    "get_sale",
    "list_sales",
    "list_open_debts",
]
