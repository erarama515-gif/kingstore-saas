"""Devices module — per-unit IMEI/serial tracking.

Inventory tracks **how many** of each product we have.
Devices tracks **which specific unit** by IMEI / serial number.

When a product is flagged ``track_by_imei=True`` (or ``track_by_serial=True``),
every physical unit of that product is registered as a ``DeviceInstance`` row
with its own lifecycle (in_stock → sold → under_repair → returned, ...).

This is the mobile-shop differentiator: scan an IMEI, instantly know
which device it is, who owns it, when it was sold, whether it's still
under warranty, and its full repair history.
"""

from app.modules.devices.service import (
    register_device,
    lookup_by_identifier,
    list_for_customer,
    list_for_product,
    mark_sold,
    mark_under_repair,
    return_from_repair,
)


__all__ = [
    "register_device",
    "lookup_by_identifier",
    "list_for_customer",
    "list_for_product",
    "mark_sold",
    "mark_under_repair",
    "return_from_repair",
]
