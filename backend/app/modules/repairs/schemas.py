"""Repairs schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import Field

from app.core.http.validation import BaseSchema


class RepairCreate(BaseSchema):
    branch_id: uuid.UUID
    customer_id: Optional[uuid.UUID] = None
    customer_name: str = Field(min_length=1, max_length=200)
    customer_phone: Optional[str] = Field(default=None, max_length=50)
    device_model: str = Field(min_length=1, max_length=200)
    imei: Optional[str] = Field(default=None, max_length=50)
    problem: str = Field(min_length=1, max_length=500)
    estimated_cost: Decimal = Field(default=Decimal("0"), ge=Decimal("0"), max_digits=14, decimal_places=2)
    notes: Optional[str] = Field(default=None, max_length=1000)


class RepairStatusUpdate(BaseSchema):
    status: str = Field(pattern="^(received|in_progress|done|canceled)$")
    notes: Optional[str] = Field(default=None, max_length=1000)


class RepairDeliverRequest(BaseSchema):
    actual_cost: Decimal = Field(ge=Decimal("0"), max_digits=14, decimal_places=2)
    is_paid: bool = True
    payment_method: str = Field(default="cash", pattern="^(cash|bank)$")
    delivery_date: Optional[date] = None
    notes: Optional[str] = Field(default=None, max_length=1000)


class RepairResponse(BaseSchema):
    id: uuid.UUID
    ticket_number: str
    branch_id: uuid.UUID
    customer_id: Optional[uuid.UUID]
    customer_name: str
    customer_phone: Optional[str]
    device_model: str
    imei: Optional[str]
    problem: str
    estimated_cost: Decimal
    actual_cost: Decimal
    status: str
    date_in: date
    date_delivered: Optional[date]
    is_paid_on_delivery: bool
    notes: Optional[str]
    delivery_journal_entry_id: Optional[uuid.UUID]
    created_at: datetime
