"""Sales Pydantic schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import Field, model_validator

from app.core.http.validation import BaseSchema


class SaleLineInput(BaseSchema):
    product_id: Optional[uuid.UUID] = None
    description: Optional[str] = Field(default=None, max_length=300)
    qty: int = Field(gt=0)
    unit_price: Decimal = Field(ge=Decimal("0"), max_digits=14, decimal_places=2)
    discount: Decimal = Field(default=Decimal("0"), ge=Decimal("0"), max_digits=14, decimal_places=2)
    is_service: bool = False
    # IMEI/Serial tracking: specific device unit being sold. Required by the
    # service when the product is tracked. Cardinality is 1 device per line —
    # if the cashier sells 2 phones, that's 2 lines.
    device_instance_id: Optional[uuid.UUID] = None

    @model_validator(mode="after")
    def _need_product_or_desc(self) -> "SaleLineInput":
        if not self.product_id and not (self.description and self.description.strip()):
            raise ValueError("Each line needs product_id or description.")
        if self.is_service and self.product_id:
            raise ValueError("Service lines cannot reference a product_id.")
        if self.device_instance_id and self.qty != 1:
            raise ValueError(
                "Tracked device lines must have qty=1 (one IMEI per line)."
            )
        return self


class SaleCreate(BaseSchema):
    branch_id: uuid.UUID
    customer_id: Optional[uuid.UUID] = None
    customer_name: Optional[str] = Field(default=None, max_length=200)
    sale_date: Optional[date] = None
    lines: list[SaleLineInput] = Field(min_length=1, max_length=200)
    paid_amount: Decimal = Field(default=Decimal("0"), ge=Decimal("0"), max_digits=14, decimal_places=2)
    notes: Optional[str] = Field(default=None, max_length=500)


class PaymentRequest(BaseSchema):
    amount: Decimal = Field(gt=Decimal("0"), max_digits=14, decimal_places=2)
    payment_date: Optional[date] = None
    method: str = Field(default="cash", pattern="^(cash|bank)$")
    notes: Optional[str] = Field(default=None, max_length=300)


# --- Responses ---

class SaleLineResponse(BaseSchema):
    id: uuid.UUID
    product_id: Optional[uuid.UUID]
    description: str
    qty: int
    unit_price: Decimal
    discount: Decimal
    line_total: Decimal
    cost_snapshot: Decimal
    is_service: bool
    # IMEI tracking — populated when the line sold a tracked device
    device_instance_id: Optional[uuid.UUID] = None
    device_imei: Optional[str] = None
    device_serial: Optional[str] = None
    warranty_ends_at: Optional[date] = None


class SalePaymentResponse(BaseSchema):
    id: uuid.UUID
    amount: Decimal
    payment_date: date
    method: str
    notes: Optional[str]


class SaleResponse(BaseSchema):
    id: uuid.UUID
    sale_number: str
    branch_id: uuid.UUID
    customer_id: Optional[uuid.UUID]
    customer_name: Optional[str]
    sale_date: date
    subtotal: Decimal
    discount_total: Decimal
    total: Decimal
    paid_amount: Decimal
    is_paid: bool
    status: str
    notes: Optional[str]
    lines: list[SaleLineResponse]
    created_at: datetime
