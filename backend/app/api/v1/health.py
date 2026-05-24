"""Health & readiness endpoints.

* ``/api/v1/health``    — liveness, always responds quickly with app version.
* ``/api/v1/ready``     — readiness, checks DB + Redis connectivity.

Kept public (no auth) so load balancers and uptime probes can hit them.
"""

from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, current_app
from sqlalchemy import text

from app import __version__
from app.core.http.responses import ok
from app.extensions import db, redis_client


health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
def health() -> tuple:
    return ok(
        {
            "status": "ok",
            "service": current_app.config.get("APP_NAME", "kingstore-saas"),
            "version": __version__,
            "time": datetime.now(timezone.utc).isoformat(),
        }
    )


@health_bp.get("/ready")
def ready() -> tuple:
    checks: dict[str, str] = {}
    overall_ok = True

    try:
        db.session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001 - readiness must report not raise
        checks["database"] = f"error: {exc.__class__.__name__}"
        overall_ok = False

    # Redis is OPTIONAL — if REDIS_URL is empty the client stays None on
    # purpose and we should report ``disabled`` (informational), not error.
    if redis_client is None:
        if current_app.config.get("REDIS_URL"):
            # URL provided but client failed to initialize — that IS a problem.
            checks["redis"] = "error: not initialized"
            overall_ok = False
        else:
            checks["redis"] = "disabled"
    else:
        try:
            redis_client.ping()
            checks["redis"] = "ok"
        except Exception as exc:  # noqa: BLE001
            checks["redis"] = f"error: {exc.__class__.__name__}"
            overall_ok = False

    body = {
        "status": "ok" if overall_ok else "degraded",
        "checks": checks,
        "time": datetime.now(timezone.utc).isoformat(),
    }
    return ok(body, status=200 if overall_ok else 503)
