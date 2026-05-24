"""Products Pydantic schemas.

Money fields use ``Decimal`` (serialized as string) so the client can't
introduce float drift.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import Field

from app.core.http.validation import BaseSchema
from app.modules.products.models import ProductCategory


# --- Requests ---------------------------------------------------------------

class ProductCreate(BaseSchema):
    name: str = Field(min_length=1, max_length=200)
    name_ar: Optional[str] = Field(default=None, max_length=200)
    category: ProductCategory = ProductCategory.other
    code: Optional[str] = Field(default=None, max_length=50)
    barcode: Optional[str] = Field(default=None, max_length=50)
    cost: Decimal = Field(default=Decimal("0"), ge=Decimal("0"), max_digits=14, decimal_places=2)
    price: Decimal = Field(default=Decimal("0"), ge=Decimal("0"), max_digits=14, decimal_places=2)
    reorder_point: int = Field(default=0, ge=0)
    track_by_imei: bool = False
    track_by_serial: bool = False
    warranty_period_days: int = Field(default=0, ge=0, le=3650)
    description: Optional[str] = Field(default=None, max_length=500)


class ProductUpdate(BaseSchema):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    name_ar: Optional[str] = Field(default=None, max_length=200)
    category: Optional[ProductCategory] = None
    code: Optional[str] = Field(default=None, max_length=50)
    barcode: Optional[str] = Field(default=None, max_length=50)
    cost: Optional[Decimal] = Field(default=None, ge=Decimal("0"), max_digits=14, decimal_places=2)
    price: Optional[Decimal] = Field(default=None, ge=Decimal("0"), max_digits=14, decimal_places=2)
    reorder_point: Optional[int] = Field(default=None, ge=0)
    track_by_imei: Optional[bool] = None
    track_by_serial: Optional[bool] = None
    warranty_period_days: Optional[int] = Field(default=None, ge=0, le=3650)
    is_active: Optional[bool] = None
    description: Optional[str] = Field(default=None, max_length=500)


# --- Responses --------------------------------------------------------------

class ProductResponse(BaseSchema):
    id: uuid.UUID
    name: str
    name_ar: Optional[str]
    category: str
    code: Optional[str]
    barcode: Optional[str]
    cost: Decimal
    price: Decimal
    reorder_point: int
    track_by_imei: bool = False
    track_by_serial: bool = False
    warranty_period_days: int = 0
    is_active: bool
    description: Optional[str]
    created_at: datetime
    updated_at: datetime


class ProductWithStock(ProductResponse):
    """Product enriched with current stock-on-hand at a given branch.

    The inventory module joins this together; defined here so the
    response type lives next to its siblings.
    """

    qty_on_hand: int = 0
    branch_id: Optional[uuid.UUID] = None
