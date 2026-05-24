"""Flask extension singletons.

Defining them at module scope (not inside ``create_app``) keeps imports simple
across the codebase: any module can do ``from app.extensions import db`` without
pulling the application factory into scope.

``init_extensions(app)`` wires each extension to the app instance.
"""

from __future__ import annotations

import redis
from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

from app.core.db.base import Base


# --- Singletons -------------------------------------------------------------

db = SQLAlchemy(model_class=Base)
migrate = Migrate()
jwt = JWTManager()
cors = CORS()
limiter = Limiter(key_func=get_remote_address)

# Redis client is plain (not a Flask extension). Created in init_extensions
# once we know the URL from config.
redis_client: redis.Redis | None = None


def init_extensions(app: Flask) -> None:
    """Bind extension singletons to the running Flask app."""
    global redis_client

    db.init_app(app)
    migrate.init_app(app, db, directory="migrations")
    jwt.init_app(app)
    cors.init_app(
        app,
        resources={r"/api/*": {"origins": app.config.get("CORS_ORIGINS", [])}},
        supports_credentials=True,
    )
    limiter.init_app(app)

    redis_url = app.config.get("REDIS_URL")
    if redis_url:
        redis_client = redis.from_url(redis_url, decode_responses=True)
    else:
        redis_client = None
    app.extensions["redis"] = redis_client

    _register_jwt_callbacks(app)


def _register_jwt_callbacks(app: Flask) -> None:
    """Wire flask-jwt-extended callbacks that need access to the DB.

    Done here (after ``jwt.init_app``) so the auth module's models and
    repository are already importable. Avoids circular-import gymnastics in
    ``app/__init__.py``.
    """
    # Local import to dodge the cycle: extensions → auth.service → extensions.
    from app.modules.auth.service import is_jti_revoked

    @jwt.token_in_blocklist_loader
    def _token_in_blocklist(_jwt_header, jwt_payload) -> bool:  # type: ignore[no-untyped-def]
        return is_jti_revoked(jwt_payload.get("jti", ""))
