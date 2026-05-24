"""Shared pytest fixtures.

These fixtures are intentionally minimal in F1. As modules land, each module
contributes its own fixtures under ``tests/<module>/conftest.py``.
"""

from __future__ import annotations

import os
from typing import Iterator

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app import create_app
from app.extensions import db as _db


@pytest.fixture(scope="session")
def app() -> Iterator[Flask]:
    """Build a Flask app configured for the testing environment."""
    os.environ["KINGSTORE_CONFIG"] = "testing"
    application = create_app("testing")

    with application.app_context():
        # Tests assume a clean schema. Caller can opt out with a marker if needed.
        _db.create_all()
        yield application
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def client(app: Flask) -> FlaskClient:
    return app.test_client()


@pytest.fixture()
def db_session(app: Flask):
    """Per-test transaction. Rolled back at the end so tests don't pollute
    each other."""
    with app.app_context():
        connection = _db.engine.connect()
        txn = connection.begin()

        # Bind the session to the inner connection so commits roll back.
        _db.session.bind = connection  # type: ignore[attr-defined]
        try:
            yield _db.session
        finally:
            _db.session.remove()
            txn.rollback()
            connection.close()
