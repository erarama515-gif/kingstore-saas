"""Gunicorn / WSGI entrypoint.

Gunicorn is launched as ``gunicorn app.wsgi:app`` from the Dockerfile.
"""

from __future__ import annotations

from app import create_app


app = create_app()
