"""Standardized JSON response envelopes.

All list endpoints return:
    {"data": [...], "pagination": {...}, "meta": {...}}

All single-resource endpoints return:
    {"data": {...}, "meta": {...}}

Errors are handled by ``app.core.errors`` and have their own envelope.
"""

from __future__ import annotations

from typing import Any

from flask import jsonify


def ok(data: Any, *, status: int = 200, meta: dict[str, Any] | None = None) -> tuple[Any, int]:
    body: dict[str, Any] = {"data": data}
    if meta:
        body["meta"] = meta
    return jsonify(body), status


def created(data: Any, *, meta: dict[str, Any] | None = None) -> tuple[Any, int]:
    return ok(data, status=201, meta=meta)


def no_content() -> tuple[str, int]:
    return "", 204


def paged(payload: dict[str, Any], *, meta: dict[str, Any] | None = None) -> tuple[Any, int]:
    """Wrap the dict returned by ``paginate_offset`` into the standard envelope."""
    body: dict[str, Any] = {
        "data": payload["items"],
        "pagination": payload["pagination"],
    }
    if meta:
        body["meta"] = meta
    return jsonify(body), 200
