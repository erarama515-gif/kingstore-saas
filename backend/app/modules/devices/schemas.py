"""Pydantic schemas for the devices module."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import Field, model_validator

from app.core.http.validation import BaseSchema


# --- Requests ---------------------------------------------------------------

class DeviceRegister(BaseSchema):
    """Add a new device instance to inventory (e.g. when receiving a phone)."""

    product_id: uuid.UUID
    branch_id: uuid.UUID
    imei: Optional[str] = Field(default=None, min_length=8, max_length=20)
    serial_number: Optional[str] = Field(default=None, max_length=80)
    purchase_cost: Decimal = Field(
        default=Decimal("0"), ge=Decimal("0"), max_digits=14, decimal_places=2
    )
    notes: Optional[str] = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _need_identifier(self) -> "DeviceRegister":
        if not self.imei and not self.serial_number:
            raise ValueError("Either imei or serial_number is required.")
        if self.imei and not self.imei.strip().isdigit():
            raise ValueError("IMEI must be digits only.")
        return self


class DeviceUpdate(BaseSchema):
    branch_id: Optional[uuid.UUID] = None
    notes: Optional[str] = Field(default=None, max_length=500)
    warranty_ends_at: Optional[date] = None


# --- Responses --------------------------------------------------------------

class DeviceResponse(BaseSchema):
    id: uuid.UUID
    product_id: uuid.UUID
    product_name: Optional[str] = None
    branch_id: Optional[uuid.UUID]
    imei: Optional[str]
    serial_number: Optional[str]
    status: str
    customer_id: Optional[uuid.UUID]
    customer_name: Optional[str] = None
    sale_id: Optional[uuid.UUID]
    sold_at: Optional[datetime]
    warranty_ends_at: Optional[date]
    is_under_warranty: bool = False
    purchase_cost: Decimal
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime


class DeviceLookupResult(BaseSchema):
    """Rich payload returned by /devices/lookup — joins everything useful."""

    device: DeviceResponse
    recent_repairs: list[dict] = []      # last few repair tickets
    sale: Optional[dict] = None          # originating sale summary, if any
