"""Alembic environment.

Run via ``flask db upgrade`` / ``flask db migrate`` (Flask-Migrate wires the
config and metadata for us). This env.py is structured to also work with raw
``alembic`` calls for ETL/CI scenarios.
"""

from __future__ import annotations

import logging
from logging.config import fileConfig

from alembic import context
from flask import current_app
from sqlalchemy import engine_from_config, pool


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)
log = logging.getLogger("alembic.env")


def _get_metadata():
    """Pull the SQLAlchemy MetaData from the Flask app context."""
    # Importing here triggers ``app.modules.__init__`` which registers every
    # model on Base.metadata.
    import app.modules  # noqa: F401

    return current_app.extensions["migrate"].db.metadata


def _get_url() -> str:
    return current_app.config["SQLALCHEMY_DATABASE_URI"]


def run_migrations_offline() -> None:
    """'Offline' mode: emit SQL to stdout without a live DB connection."""
    context.configure(
        url=_get_url(),
        target_metadata=_get_metadata(),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        render_as_batch=False,  # Postgres doesn't need batch mode
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Standard online mode against a live engine."""
    cfg = config.get_section(config.config_ini_section, {})
    cfg["sqlalchemy.url"] = _get_url()

    connectable = engine_from_config(
        cfg,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=_get_metadata(),
            compare_type=True,
            compare_server_default=True,
            render_as_batch=False,
            include_schemas=False,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
