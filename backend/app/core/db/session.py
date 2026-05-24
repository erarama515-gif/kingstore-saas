"""Session helpers.

For 99% of request handling, ``db.session`` from ``app.extensions`` is what
you want. This module exists for the corner cases:

* CLI / Celery tasks that need an explicit transaction boundary
* Background jobs that span multiple commits
* ETL scripts that want to bypass tenant scoping
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy.orm import Session

from app.extensions import db


@contextmanager
def session_scope() -> Iterator[Session]:
    """Atomic unit-of-work over the request-scoped session.

    Commits on clean exit, rolls back on exception, never closes the session
    (Flask-SQLAlchemy manages that at request teardown).
    """
    session: Session = db.session
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise


@contextmanager
def unscoped_session() -> Iterator[Session]:
    """A session that bypasses automatic tenant filtering for one block.

    Use sparingly. Intended for admin tooling, cross-tenant analytics, and
    the SQLite → Postgres ETL.
    """
    session: Session = db.session
    # ``execution_options`` on the session is inherited by statements executed
    # through it; the tenant-scope event listener checks for the flag.
    session.info["skip_tenant_filter"] = True
    try:
        with session.no_autoflush:
            yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.info.pop("skip_tenant_filter", None)
