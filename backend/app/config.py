"""Environment-driven configuration.

All env vars are read once at import time of the chosen config class. The
class itself is registered into ``app.config`` so request handlers can access
it via ``current_app.config[...]``.
"""

from __future__ import annotations

import os
from datetime import timedelta
from typing import Optional

from dotenv import load_dotenv


# Load .env once at import. In Docker, env comes from compose; this is a no-op.
load_dotenv()


def _bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int(value: Optional[str], default: int) -> int:
    try:
        return int(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _csv(value: Optional[str]) -> list[str]:
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]


class BaseConfig:
    """Shared defaults; subclasses override per environment."""

    # --- App ---
    APP_NAME = os.getenv("APP_NAME", "kingstore-saas")
    APP_TIMEZONE = os.getenv("APP_TIMEZONE", "Africa/Cairo")

    # --- Secrets ---
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-insecure-replace-me")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", SECRET_KEY)
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        minutes=_int(os.getenv("JWT_ACCESS_TTL_MINUTES"), 15)
    )
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(
        days=_int(os.getenv("JWT_REFRESH_TTL_DAYS"), 7)
    )
    JWT_TOKEN_LOCATION = ["headers"]
    JWT_HEADER_TYPE = "Bearer"

    # --- Database ---
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://kingstore:kingstore@db:5432/kingstore",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = _bool(os.getenv("SQLALCHEMY_ECHO"), False)
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 1800,
        "pool_size": _int(os.getenv("DB_POOL_SIZE"), 10),
        "max_overflow": _int(os.getenv("DB_MAX_OVERFLOW"), 20),
    }

    # --- Redis / Celery (OPTIONAL — postponed for MVP) ---
    # Leave REDIS_URL unset to skip Redis entirely; the limiter falls back to
    # in-memory storage and brute-force lockout silently degrades.
    REDIS_URL = os.getenv("REDIS_URL", "").strip() or None
    CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "").strip() or None
    CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "").strip() or None

    # --- CORS ---
    CORS_ORIGINS = _csv(os.getenv("CORS_ORIGINS", "http://localhost:3000"))

    # --- Rate limiting ---
    # If REDIS_URL is set, use redis://...; otherwise memory:// (good enough
    # for single-process dev; switch to Redis in prod via env).
    _ratelimit_default_storage = (
        os.getenv("RATELIMIT_STORAGE_URI")
        or (os.getenv("REDIS_URL", "").strip() and os.getenv("REDIS_URL", "").rstrip("/") + "/3")
        or "memory://"
    )
    RATELIMIT_STORAGE_URI = _ratelimit_default_storage
    RATELIMIT_DEFAULT = os.getenv("RATELIMIT_DEFAULT", "200 per minute")
    RATELIMIT_HEADERS_ENABLED = True

    # --- Logging ---
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT = os.getenv("LOG_FORMAT", "text")

    # --- Storage ---
    STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local")
    LOCAL_STORAGE_ROOT = os.getenv("LOCAL_STORAGE_ROOT", "/app/storage")

    # --- Feature flags (foundation; expand per phase) ---
    AUDIT_LOG_ENABLED = True
    SOFT_DELETE_ENABLED = True


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    TESTING = False
    SQLALCHEMY_ECHO = _bool(os.getenv("SQLALCHEMY_ECHO"), False)


class ProductionConfig(BaseConfig):
    DEBUG = False
    TESTING = False

    def __init__(self) -> None:
        # Fail fast if production secrets weren't set.
        for required in ("SECRET_KEY", "JWT_SECRET_KEY"):
            if os.getenv(required, "").startswith("dev-") or not os.getenv(required):
                raise RuntimeError(
                    f"{required} must be set to a non-default value in production"
                )


class TestingConfig(BaseConfig):
    DEBUG = False
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+psycopg2://kingstore:kingstore@db:5432/kingstore_test",
    )
    RATELIMIT_ENABLED = False
    # Make JWT exp predictable in tests
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=5)


_CONFIG_MAP: dict[str, type[BaseConfig]] = {
    "development": DevelopmentConfig,
    "dev": DevelopmentConfig,
    "production": ProductionConfig,
    "prod": ProductionConfig,
    "testing": TestingConfig,
    "test": TestingConfig,
}


def get_config(name: Optional[str] = None) -> BaseConfig:
    """Resolve a config class by short name. Defaults to development."""
    key = (name or "development").strip().lower()
    cls = _CONFIG_MAP.get(key, DevelopmentConfig)
    # ProductionConfig validates env in __init__; others are stateless.
    return cls() if cls is ProductionConfig else cls()
