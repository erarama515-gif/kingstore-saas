"""Application factory and module entry point.

This package is intentionally tiny — actual wiring lives in ``app.config``,
``app.extensions``, and the per-module blueprints under ``app.modules``.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from flask import Flask

from app.config import get_config
from app.extensions import init_extensions
from app.core.errors import register_error_handlers
from app.core.tenant_context import register_tenant_hooks
from app.core.security.headers import register_security_headers
from app.api.v1 import api_v1_bp


__version__ = "0.1.0"


def create_app(config_name: Optional[str] = None) -> Flask:
    """Application factory.

    Args:
        config_name: One of "development", "production", "testing".
            If None, derived from FLASK_ENV / KINGSTORE_CONFIG env var.

    Returns:
        Configured Flask application ready to serve requests.
    """
    app = Flask(__name__, instance_relative_config=False)

    cfg = get_config(config_name or os.getenv("KINGSTORE_CONFIG") or os.getenv("FLASK_ENV"))
    app.config.from_object(cfg)

    _configure_logging(app)

    # Order matters: extensions first (db, jwt, redis, ...), then hooks that
    # depend on them (tenant context reads JWT claims), then blueprints.
    init_extensions(app)
    register_security_headers(app)
    register_tenant_hooks(app)
    register_error_handlers(app)

    app.register_blueprint(api_v1_bp)

    _register_cli(app)

    app.logger.info("kingstore-saas initialized", extra={"config": cfg.__class__.__name__})
    return app


def _configure_logging(app: Flask) -> None:
    """Wire structured logging based on LOG_FORMAT/LOG_LEVEL env."""
    level = app.config.get("LOG_LEVEL", "INFO")
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    app.logger.setLevel(level)


def _register_cli(app: Flask) -> None:
    """Register custom flask CLI commands.

    Empty for now. Phase F2 will add ``flask seed bootstrap`` etc.
    """
    # Placeholder; concrete commands land with their owning modules.
    pass
