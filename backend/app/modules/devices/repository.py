"""Devices repository — DB access only, no business rules."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from app.modules.devices.models import DeviceInstance, DeviceStatus


def get_by_id(session: Session, device_id: uuid.UUID) -> Optional[DeviceInstance]:
    return session.get(DeviceInstance, device_id)


def find_by_identifier(
    session: Session, *, tenant_id: uuid.UUID, identifier: str
) -> Optional[DeviceInstance]:
    """Look up by IMEI OR serial number — whichever matches."""
    q = identifier.strip()
    if not q:
        return None
    return session.execute(
        select(DeviceInstance).where(
            DeviceInstance.tenant_id == tenant_id,
            DeviceInstance.deleted_at.is_(None),
            or_(DeviceInstance.imei == q, DeviceInstance.serial_number == q),
        )
    ).scalar_one_or_none()


def list_for_customer(
    session: Session, *, tenant_id: uuid.UUID, customer_id: uuid.UUID
) -> list[DeviceInstance]:
    return list(
        session.execute(
            select(DeviceInstance)
            .where(
                DeviceInstance.tenant_id == tenant_id,
                DeviceInstance.customer_id == customer_id,
                DeviceInstance.deleted_at.is_(None),
            )
            .order_by(DeviceInstance.sold_at.desc().nullslast())
        ).scalars().all()
    )


def list_for_product(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    product_id: uuid.UUID,
    status: Optional[DeviceStatus] = None,
) -> list[DeviceInstance]:
    stmt = (
        select(DeviceInstance)
        .where(
            DeviceInstance.tenant_id == tenant_id,
            DeviceInstance.product_id == product_id,
            DeviceInstance.deleted_at.is_(None),
        )
        .order_by(DeviceInstance.created_at.desc())
    )
    if status is not None:
        stmt = stmt.where(DeviceInstance.status == status)
    return list(session.execute(stmt).scalars().all())


def search_query(
    *,
    tenant_id: uuid.UUID,
    q: Optional[str] = None,
    status: Optional[DeviceStatus] = None,
    branch_id: Optional[uuid.UUID] = None,
    customer_id: Optional[uuid.UUID] = None,
    product_id: Optional[uuid.UUID] = None,
) -> Select:
    stmt = (
        select(DeviceInstance)
        .where(
            DeviceInstance.tenant_id == tenant_id,
            DeviceInstance.deleted_at.is_(None),
        )
        .order_by(DeviceInstance.created_at.desc())
    )
    if q:
        term = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                DeviceInstance.imei.ilike(term),
                DeviceInstance.serial_number.ilike(term),
            )
        )
    if status is not None:
        stmt = stmt.where(DeviceInstance.status == status)
    if branch_id is not None:
        stmt = stmt.where(DeviceInstance.branch_id == branch_id)
    if customer_id is not None:
        stmt = stmt.where(DeviceInstance.customer_id == customer_id)
    if product_id is not None:
        stmt = stmt.where(DeviceInstance.product_id == product_id)
    return stmt


def add(session: Session, device: DeviceInstance) -> DeviceInstance:
    session.add(device)
    session.flush()
    return device
