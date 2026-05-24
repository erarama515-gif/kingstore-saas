"""Centralized JSON error responses.

Goals:
* Every error — HTTPException, validation, integrity, unexpected — returns
  the same JSON envelope so the frontend can rely on it.
* No stack traces in responses, ever (logged server-side).
* Validation errors enumerate the offending fields so the UI can surface them.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from flask import Flask, jsonify
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, NoResultFound, SQLAlchemyError
from werkzeug.exceptions import HTTPException


log = logging.getLogger(__name__)


def _envelope(code: str, message: str, status: int, details: Any | None = None) -> tuple[Any, int]:
    body: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
            "trace_id": uuid.uuid4().hex,
        }
    }
    if details is not None:
        body["error"]["details"] = details
    return jsonify(body), status


def register_error_handlers(app: Flask) -> None:
    """Wire all error handlers onto the app."""

    @app.errorhandler(HTTPException)
    def _http(e: HTTPException) -> tuple[Any, int]:
        code = (e.name or "http_error").lower().replace(" ", "_")
        return _envelope(code, e.description or e.name or "HTTP error", e.code or 500)

    @app.errorhandler(ValidationError)
    def _validation(e: ValidationError) -> tuple[Any, int]:
        return _envelope(
            "validation_error",
            "Request payload failed validation.",
            422,
            details=[
                {
                    "loc": list(err.get("loc", [])),
                    "msg": err.get("msg"),
                    "type": err.get("type"),
                }
                for err in e.errors()
            ],
        )

    @app.errorhandler(NoResultFound)
    def _not_found(_: NoResultFound) -> tuple[Any, int]:
        return _envelope("not_found", "Resource not found.", 404)

    @app.errorhandler(IntegrityError)
    def _integrity(e: IntegrityError) -> tuple[Any, int]:
        log.warning("integrity_error", extra={"orig": str(e.orig)})
        return _envelope(
            "conflict",
            "Database constraint violated.",
            409,
        )

    @app.errorhandler(SQLAlchemyError)
    def _sa(e: SQLAlchemyError) -> tuple[Any, int]:
        log.exception("sqlalchemy_error")
        return _envelope("database_error", "Database error.", 500)

    @app.errorhandler(Exception)
    def _unhandled(e: Exception) -> tuple[Any, int]:
        # Let werkzeug HTTPExceptions through to the dedicated handler above.
        if isinstance(e, HTTPException):
            return _http(e)
        log.exception("unhandled_exception")
        return _envelope("internal_error", "Internal server error.", 500)
