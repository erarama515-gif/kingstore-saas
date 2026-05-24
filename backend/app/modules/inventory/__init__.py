"""Inventory module.

Tracks *how much* of each product is at each branch (``StockLevel``) and
keeps an immutable history of every movement (``StockMovement``).

Public surface is the ``service`` module. Other code never touches the
StockLevel/StockMovement tables directly — the service layer is the only
writer, and it's the place where atomicity (SELECT FOR UPDATE) and the
matching accounting journal entry live in the same transaction.
"""

from app.modules.inventory.service import (
    adjust_stock,
    decrement_for_sale,
    increment_for_purchase,
    increment_for_return,
    get_stock_level,
    list_levels_for_branch,
    list_movements_for_product,
    open_or_create_level,
)


__all__ = [
    "adjust_stock",
    "decrement_for_sale",
    "increment_for_purchase",
    "increment_for_return",
    "get_stock_level",
    "list_levels_for_branch",
    "list_movements_for_product",
    "open_or_create_level",
]
