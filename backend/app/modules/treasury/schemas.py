"""Treasury schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import Field

from app.core.http.validation import BaseSchema


class CloseDayRequest(BaseSchema):
    branch_id: uuid.UUID
    business_date: Optional[date] = None
    counted_cash: Decimal = Field(ge=Decimal("0"), max_digits=14, decimal_places=2)
    notes: Optional[str] = Field(default=None, max_length=500)


class DayCloseResponse(BaseSchema):
    id: uuid.UUID
    branch_id: uuid.UUID
    business_date: date
    opening_cash: Decimal
    cash_in: Decimal
    cash_out: Decimal
    expected_cash: Decimal
    counted_cash: Decimal
    variance: Decimal
    notes: Optional[str]
    closed_at: datetime


class CashPositionResponse(BaseSchema):
    cash_balance: Decimal
    bank_balance: Decimal
    today_cash_in: Decimal
    today_cash_out: Decimal
    today_net: Decimal
    business_date: date
