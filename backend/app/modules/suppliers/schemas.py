"""Suppliers Pydantic schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import EmailStr, Field

from app.core.http.validation import BaseSchema


class SupplierCreate(BaseSchema):
    name: str = Field(min_length=1, max_length=200)
    name_ar: Optional[str] = Field(default=None, max_length=200)
    phone: Optional[str] = Field(default=None, max_length=50)
    email: Optional[EmailStr] = None
    contact_person: Optional[str] = Field(default=None, max_length=200)
    address: Optional[str] = Field(default=None, max_length=500)
    notes: Optional[str] = Field(default=None, max_length=1000)

    # Opening AP balance (money we already owe at create time).
    # Posts: DR Owner's Capital / CR AP (tagged supplier).
    opening_balance: Decimal = Field(
        default=Decimal("0"), ge=Decimal("0"), max_digits=14, decimal_places=2,
    )
    opening_balance_date: Optional[date] = None


class SupplierUpdate(BaseSchema):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    name_ar: Optional[str] = Field(default=None, max_length=200)
    phone: Optional[str] = Field(default=None, max_length=50)
    email: Optional[EmailStr] = None
    contact_person: Optional[str] = Field(default=None, max_length=200)
    address: Optional[str] = Field(default=None, max_length=500)
    notes: Optional[str] = Field(default=None, max_length=1000)
    is_active: Optional[bool] = None


class SupplierResponse(BaseSchema):
    id: uuid.UUID
    name: str
    name_ar: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    contact_person: Optional[str]
    address: Optional[str]
    notes: Optional[str]
    total_purchased_cached: Decimal
    payable_cached: Decimal
    last_txn_at: Optional[datetime]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SupplierQuickHit(BaseSchema):
    id: uuid.UUID
    name: str
    name_ar: Optional[str]
    phone: Optional[str]
    payable: Decimal


class SupplierBalanceResponse(BaseSchema):
    supplier_id: uuid.UUID
    payable: Decimal
    total_purchased: Decimal
    last_txn_at: Optional[datetime]


class SupplierStatementLine(BaseSchema):
    journal_entry_id: uuid.UUID
    entry_date: date
    source: str
    reference: Optional[str]
    description: Optional[str]
    debit: Decimal
    credit: Decimal
    running_balance: Decimal      # AP balance: credit-positive


class SupplierStatementResponse(BaseSchema):
    supplier_id: uuid.UUID
    supplier_name: str
    opening_balance: Decimal
    closing_balance: Decimal
    lines: list[SupplierStatementLine]
