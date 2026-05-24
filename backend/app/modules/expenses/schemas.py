"""Expenses Pydantic schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import Field

from app.core.http.validation import BaseSchema


class ExpenseCreate(BaseSchema):
    branch_id: uuid.UUID
    expense_date: Optional[date] = None
    # Either pick an account by id OR by system_key (e.g. "RENT", "SALARIES").
    expense_account_id: Optional[uuid.UUID] = None
    expense_account_key: Optional[str] = Field(default=None, max_length=50)
    amount: Decimal = Field(gt=Decimal("0"), max_digits=14, decimal_places=2)
    payment_method: str = Field(default="cash", pattern="^(cash|bank)$")
    description: str = Field(min_length=1, max_length=300)
    reference: Optional[str] = Field(default=None, max_length=100)
    notes: Optional[str] = Field(default=None, max_length=1000)


class ExpenseResponse(BaseSchema):
    id: uuid.UUID
    branch_id: uuid.UUID
    expense_date: date
    expense_account_id: uuid.UUID
    amount: Decimal
    payment_method: str
    description: str
    reference: Optional[str]
    notes: Optional[str]
    journal_entry_id: Optional[uuid.UUID]
    created_at: datetime
