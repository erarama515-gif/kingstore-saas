"""Pydantic-based request validation.

Routes typically do:

    from app.core.http.validation import parse_json, parse_query
    payload = parse_json(MySchema)
    filters = parse_query(MyFilters)

``ValidationError`` raised by Pydantic is caught by the centralized error
handler and turned into a 422 with structured ``details``.
"""

from __future__ import annotations

from typing import TypeVar

from flask import request
from pydantic import BaseModel


T = TypeVar("T", bound=BaseModel)


class BaseSchema(BaseModel):
    """Shared schema base. Forbid extra fields by default — prevents silent
    typos in payloads from being ignored."""

    model_config = {
        "extra": "forbid",
        "str_strip_whitespace": True,
        "from_attributes": True,
    }


def parse_json(schema: type[T]) -> T:
    """Validate the JSON body against ``schema``.

    Pydantic raises ``ValidationError`` on failure; the global handler turns
    that into a 422 response.
    """
    data = request.get_json(silent=True) or {}
    return schema.model_validate(data)


def parse_query(schema: type[T]) -> T:
    """Validate query-string args against ``schema``."""
    return schema.model_validate(dict(request.args))
