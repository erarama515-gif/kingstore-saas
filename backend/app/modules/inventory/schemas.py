"""Inventory Pydantic schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import Field, model_validator

from app.core.http.validation import BaseSchema
from app.modules.inventory.models import MovementType


# --- Requests ---------------------------------------------------------------

class StockAdjustmentRequest(BaseSchema):
    """Manual adjustment by a warehouse manager.

    ``qty`` is positive; ``direction`` chooses inbound (e.g. opening stock,
    found inventory) vs outbound (damage, shrinkage). The matching journal
    entry hits Inventory and the configured counterparty account.
    """

    product_id: uuid.UUID
    branch_id: uuid.UUID
    qty: int = Field(gt=0)
    direction: str = Field(pattern="^(in|out)$")
    unit_cost: Optional[Decimal] = Field(
        default=None, ge=Decimal("0"), max_digits=14, decimal_places=4,
        description="Defaults to the product's standard cost when omitted.",
    )
    reason: str = Field(min_length=1, max_length=200)
    movement_date: Optional[date] = None


class PurchaseLineInput(BaseSchema):
    product_id: uuid.UUID
    qty: int = Field(gt=0)
    unit_cost: Decimal = Field(ge=Decimal("0"), max_digits=14, decimal_places=4)


class PurchaseRequest(BaseSchema):
    """Receive stock from a supplier. Posts journal: DR Inventory / CR AP-or-Cash."""

    branch_id: uuid.UUID
    supplier_id: Optional[uuid.UUID] = None      # F5 supplier; optional for MVP cash-buy
    paid_in_cash: bool = False
    movement_date: date
    reference: Optional[str] = Field(default=None, max_length=100)
    lines: list[PurchaseLineInput] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def _supplier_required_if_credit(self) -> "PurchaseRequest":
        if not self.paid_in_cash and self.supplier_id is None:
            raise ValueError(
                "supplier_id is required when paid_in_cash is False (credit purchase)."
            )
        return self


# --- Responses --------------------------------------------------------------

class StockLevelResponse(BaseSchema):
    id: uuid.UUID
    product_id: uuid.UUID
    branch_id: uuid.UUID
    qty_on_hand: int
    avg_cost: Decimal
    updated_at: datetime


class StockMovementResponse(BaseSchema):
    id: uuid.UUID
    product_id: uuid.UUID
    branch_id: uuid.UUID
    movement_type: str
    qty: int
    unit_cost: Decimal
    movement_date: date
    reference: Optional[str]
    notes: Optional[str]
    journal_entry_id: Optional[uuid.UUID]
    created_by_id: Optional[uuid.UUID]
