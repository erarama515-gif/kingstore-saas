"""Products module — the catalog.

Holds *what we sell*: name, category, identifiers (barcode/code), standard
cost and price, active flag. Does NOT hold *how much we have* — that's the
inventory module's job.

The split keeps two concerns testable in isolation: you can model the
catalog without thinking about stock, and you can move stock without
duplicating product metadata.
"""

from app.modules.products.service import (
    create_product,
    update_product,
    delete_product,
    lookup_for_pos,
    get_product,
    list_products,
)


__all__ = [
    "create_product",
    "update_product",
    "delete_product",
    "lookup_for_pos",
    "get_product",
    "list_products",
]
