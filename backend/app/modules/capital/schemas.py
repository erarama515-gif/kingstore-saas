"""Capital schemas."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import Field

from app.core.http.validation import BaseSchema


class CapitalMovementRequest(BaseSchema):
    amount: Decimal = Field(gt=Decimal("0"), max_digits=14, decimal_places=2)
    description: str = Field(min_length=1, max_length=300)
    branch_id: Optional[uuid.UUID] = None
    movement_date: Optional[date] = None
