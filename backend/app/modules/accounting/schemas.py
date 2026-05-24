"""Pydantic schemas for accounting requests/responses.

Money is exchanged as a string (Decimal-as-JSON) so the client can't accidentally
introduce float drift. Pydantic's ``Decimal`` field parses strings safely.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import Field, field_validator, model_validator

from app.core.http.validation import BaseSchema


# --- Requests ---------------------------------------------------------------

class JournalLineInput(BaseSchema):
    account_id: uuid.UUID
    debit: Decimal = Field(default=Decimal("0"), ge=Decimal("0"), max_digits=14, decimal_places=2)
    credit: Decimal = Field(default=Decimal("0"), ge=Decimal("0"), max_digits=14, decimal_places=2)
    description: Optional[str] = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _xor(self) -> "JournalLineInput":
        dr_pos = self.debit > 0
        cr_pos = self.credit > 0
        if dr_pos == cr_pos:
            raise ValueError(
                "Each line must have exactly one of debit or credit > 0 (got "
                f"debit={self.debit}, credit={self.credit})."
            )
        return self


class JournalEntryCreate(BaseSchema):
    entry_date: date
    branch_id: Optional[uuid.UUID] = None
    reference: Optional[str] = Field(default=None, max_length=50)
    description: Optional[str] = Field(default=None, max_length=500)
    lines: list[JournalLineInput] = Field(..., min_length=2, max_length=200)

    @field_validator("lines")
    @classmethod
    def _balanced(cls, lines: list[JournalLineInput]) -> list[JournalLineInput]:
        total_dr = sum((l.debit for l in lines), Decimal("0"))
        total_cr = sum((l.credit for l in lines), Decimal("0"))
        if total_dr != total_cr:
            raise ValueError(
                f"Entry not balanced: debits={total_dr}, credits={total_cr}."
            )
        if total_dr == 0:
            raise ValueError("Entry total is zero.")
        return lines


# --- Responses --------------------------------------------------------------

class AccountResponse(BaseSchema):
    id: uuid.UUID
    code: str
    name: str
    name_ar: Optional[str]
    type: str
    parent_id: Optional[uuid.UUID]
    system_key: Optional[str]
    is_active: bool


class JournalLineResponse(BaseSchema):
    id: uuid.UUID
    account_id: uuid.UUID
    debit: Decimal
    credit: Decimal
    description: Optional[str]


class JournalEntryResponse(BaseSchema):
    id: uuid.UUID
    entry_date: date
    branch_id: Optional[uuid.UUID]
    source: str
    source_ref: Optional[str]
    reference: Optional[str]
    description: Optional[str]
    posted_at: datetime
    posted_by_id: Optional[uuid.UUID]
    reverses_id: Optional[uuid.UUID]
    lines: list[JournalLineResponse]


class TrialBalanceRow(BaseSchema):
    account_id: uuid.UUID
    code: str
    name: str
    name_ar: Optional[str]
    type: str
    debit_total: Decimal
    credit_total: Decimal
    balance: Decimal  # signed using the account type's natural side


class TrialBalanceResponse(BaseSchema):
    rows: list[TrialBalanceRow]
    debit_grand_total: Decimal
    credit_grand_total: Decimal
    is_balanced: bool  # debit_grand_total == credit_grand_total
