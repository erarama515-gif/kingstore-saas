"""Customers Pydantic schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import EmailStr, Field

from app.core.http.validation import BaseSchema


# --- Requests ---------------------------------------------------------------

class CustomerCreate(BaseSchema):
    name: str = Field(min_length=1, max_length=200)
    name_ar: Optional[str] = Field(default=None, max_length=200)
    phone: Optional[str] = Field(default=None, max_length=50)
    email: Optional[EmailStr] = None
    address: Optional[str] = Field(default=None, max_length=500)
    notes: Optional[str] = Field(default=None, max_length=1000)

    # Optional opening AR balance (legacy migrations / existing debts).
    # Posts DR AR (tagged with this customer) / CR Owner's Capital.
    opening_balance: Decimal = Field(
        default=Decimal("0"), ge=Decimal("0"), max_digits=14, decimal_places=2,
        description="Money the customer already owes us at create time.",
    )
    opening_balance_date: Optional[date] = None


class CustomerUpdate(BaseSchema):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    name_ar: Optional[str] = Field(default=None, max_length=200)
    phone: Optional[str] = Field(default=None, max_length=50)
    email: Optional[EmailStr] = None
    address: Optional[str] = Field(default=None, max_length=500)
    notes: Optional[str] = Field(default=None, max_length=1000)
    is_active: Optional[bool] = None


# --- Responses --------------------------------------------------------------

class CustomerResponse(BaseSchema):
    id: uuid.UUID
    name: str
    name_ar: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    address: Optional[str]
    notes: Optional[str]
    total_spent_cached: Decimal
    debt_cached: Decimal
    visits_count: int
    last_txn_at: Optional[datetime]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CustomerQuickHit(BaseSchema):
    """POS-shaped result: minimal payload + live AR balance."""

    id: uuid.UUID
    name: str
    name_ar: Optional[str]
    phone: Optional[str]
    debt: Decimal


class CustomerBalanceResponse(BaseSchema):
    customer_id: uuid.UUID
    debt: Decimal              # current AR = SUM(debit-credit) on AR lines
    total_spent: Decimal       # cached
    visits_count: int
    last_txn_at: Optional[datetime]


class CustomerStatementLine(BaseSchema):
    journal_entry_id: uuid.UUID
    entry_date: date
    source: str
    reference: Optional[str]
    description: Optional[str]
    debit: Decimal
    credit: Decimal
    running_balance: Decimal


class CustomerStatementResponse(BaseSchema):
    customer_id: uuid.UUID
    customer_name: str
    opening_balance: Decimal
    closing_balance: Decimal
    lines: list[CustomerStatementLine]
