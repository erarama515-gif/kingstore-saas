"""Celery worker entrypoint.

Run with: ``celery -A app.celery_app.celery worker -l info``

The Celery instance is bound to a Flask app so tasks have access to the
extensions (db, redis) and tenant-aware sessions when they need them.
"""

from __future__ import annotations

from celery import Celery
from flask import Flask

from app import create_app


def _make_celery(app: Flask) -> Celery:
    celery = Celery(
        app.import_name,
        broker=app.config["CELERY_BROKER_URL"],
        backend=app.config["CELERY_RESULT_BACKEND"],
    )
    celery.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone=app.config["APP_TIMEZONE"],
        enable_utc=True,
        task_track_started=True,
        task_acks_late=True,
        worker_prefetch_multiplier=1,
    )

    class FlaskTask(celery.Task):
        """Run every task inside an app context so db.session etc. work."""

        def __call__(self, *args, **kwargs):  # type: ignore[override]
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = FlaskTask  # type: ignore[assignment]
    return celery


flask_app = create_app()
celery = _make_celery(flask_app)
