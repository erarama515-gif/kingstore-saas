"""Devices service — the only writer to ``device_instances``.

State machine
=============
``register_device(...)`` creates a new device in ``in_stock``.
``mark_sold(...)`` flips to ``sold``, sets customer + sale linkage +
warranty.
``mark_under_repair(...)`` flips a sold device to ``under_repair``.
``return_from_repair(...)`` flips back to ``sold`` (still owned) or to
``in_stock`` (returned to shop / replacement).

Sales integration is in ``sales.service`` — it calls into here.
Repairs integration is in ``repairs.service``.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import BadRequest, Conflict, NotFound

from app.extensions import db
from app.modules.devices import repository as repo
from app.modules.devices.models import DeviceInstance, DeviceStatus


log = logging.getLogger(__name__)


# --- Allowed transitions ---------------------------------------------------

_TRANSITIONS: dict[DeviceStatus, set[DeviceStatus]] = {
    DeviceStatus.in_stock:     {DeviceStatus.sold, DeviceStatus.damaged, DeviceStatus.archived},
    DeviceStatus.sold:         {DeviceStatus.under_repair, DeviceStatus.returned},
    DeviceStatus.under_repair: {DeviceStatus.sold, DeviceStatus.damaged},
    DeviceStatus.returned:     {DeviceStatus.in_stock, DeviceStatus.damaged},
    DeviceStatus.damaged:      {DeviceStatus.archived},
    DeviceStatus.archived:     set(),
}


def _assert_transition(current: DeviceStatus, target: DeviceStatus) -> None:
    if target not in _TRANSITIONS[current]:
        raise BadRequest(
            f"Invalid status transition: {current.value} → {target.value}"
        )


# --- Register --------------------------------------------------------------

def register_device(
    *,
    tenant_id: uuid.UUID,
    product_id: uuid.UUID,
    branch_id: uuid.UUID,
    imei: Optional[str] = None,
    serial_number: Optional[str] = None,
    purchase_cost: Decimal = Decimal("0"),
    notes: Optional[str] = None,
) -> DeviceInstance:
    """Create a new device instance in ``in_stock`` status."""
    if not imei and not serial_number:
        raise BadRequest("Either imei or serial_number is required.")

    # Detect existing IMEI/serial within the tenant
    existing = repo.find_by_identifier(
        db.session, tenant_id=tenant_id, identifier=(imei or serial_number) or "",
    )
    if existing is not None:
        raise Conflict(
            f"Device with this identifier already exists "
            f"(status: {existing.status.value})."
        )

    device = DeviceInstance(
        tenant_id=tenant_id,
        product_id=product_id,
        branch_id=branch_id,
        imei=(imei.strip() if imei else None),
        serial_number=(serial_number.strip() if serial_number else None),
        status=DeviceStatus.in_stock,
        purchase_cost=purchase_cost,
        notes=notes,
    )
    try:
        repo.add(db.session, device)
    except IntegrityError as exc:
        db.session.rollback()
        raise Conflict("Duplicate IMEI or serial.") from exc

    log.info(
        "device_registered",
        extra={
            "tenant_id": str(tenant_id),
            "device_id": str(device.id),
            "identifier": device.identifier(),
        },
    )
    return device


# --- State changes --------------------------------------------------------

def mark_sold(
    *,
    tenant_id: uuid.UUID,
    device_id: uuid.UUID,
    customer_id: uuid.UUID,
    sale_id: Optional[uuid.UUID] = None,
    sale_line_id: Optional[uuid.UUID] = None,
    warranty_period_days: int = 0,
    sold_on: Optional[date] = None,
) -> DeviceInstance:
    device = _load(tenant_id, device_id)
    _assert_transition(device.status, DeviceStatus.sold)
    device.status = DeviceStatus.sold
    device.customer_id = customer_id
    device.sale_id = sale_id
    device.sale_line_id = sale_line_id
    device.sold_at = datetime.now(timezone.utc)
    device.branch_id = None  # no longer in a branch's stock
    if warranty_period_days > 0:
        base = sold_on or date.today()
        device.warranty_ends_at = base + timedelta(days=warranty_period_days)
    db.session.flush()
    log.info(
        "device_sold",
        extra={"device_id": str(device.id), "customer_id": str(customer_id), "sale_id": str(sale_id)},
    )
    return device


def mark_under_repair(
    *, tenant_id: uuid.UUID, device_id: uuid.UUID
) -> DeviceInstance:
    device = _load(tenant_id, device_id)
    _assert_transition(device.status, DeviceStatus.under_repair)
    device.status = DeviceStatus.under_repair
    db.session.flush()
    return device


def return_from_repair(
    *, tenant_id: uuid.UUID, device_id: uuid.UUID
) -> DeviceInstance:
    """Repair done → device goes back to its customer (status=sold)."""
    device = _load(tenant_id, device_id)
    if device.status != DeviceStatus.under_repair:
        raise BadRequest(
            f"Device is not under repair (status={device.status.value})."
        )
    device.status = DeviceStatus.sold
    db.session.flush()
    return device


# --- Lookups (read-side) --------------------------------------------------

def lookup_by_identifier(
    *, tenant_id: uuid.UUID, identifier: str
) -> Optional[DeviceInstance]:
    return repo.find_by_identifier(db.session, tenant_id=tenant_id, identifier=identifier)


def list_for_customer(
    *, tenant_id: uuid.UUID, customer_id: uuid.UUID
) -> list[DeviceInstance]:
    return repo.list_for_customer(db.session, tenant_id=tenant_id, customer_id=customer_id)


def list_for_product(
    *,
    tenant_id: uuid.UUID,
    product_id: uuid.UUID,
    status: Optional[DeviceStatus] = None,
) -> list[DeviceInstance]:
    return repo.list_for_product(
        db.session, tenant_id=tenant_id, product_id=product_id, status=status
    )


def _load(tenant_id: uuid.UUID, device_id: uuid.UUID) -> DeviceInstance:
    d = repo.get_by_id(db.session, device_id)
    if d is None or d.tenant_id != tenant_id or d.deleted_at is not None:
        raise NotFound("Device not found.")
    return d
