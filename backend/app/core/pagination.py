"""Pagination helpers.

Two strategies supported:

* ``paginate_offset(query, page, per_page)`` — classic offset/limit, fine for
  admin tables and reports of bounded size.
* ``paginate_cursor(query, cursor_col, last_value, limit)`` — keyset for hot
  endpoints (transaction lists, audit logs) where deep pagination is required.

Routes use ``parse_page_args(request.args)`` to extract page/per_page with sane
defaults and clamps so a client can't request 1M rows per page.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from flask import request
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session


DEFAULT_PER_PAGE = 25
MAX_PER_PAGE = 200


@dataclass(slots=True)
class PageArgs:
    page: int
    per_page: int


def parse_page_args(args: Optional[Any] = None) -> PageArgs:
    src = args if args is not None else request.args
    try:
        page = max(1, int(src.get("page", 1)))
    except (TypeError, ValueError):
        page = 1
    try:
        per_page = int(src.get("per_page", DEFAULT_PER_PAGE))
    except (TypeError, ValueError):
        per_page = DEFAULT_PER_PAGE
    per_page = max(1, min(per_page, MAX_PER_PAGE))
    return PageArgs(page=page, per_page=per_page)


def paginate_offset(
    session: Session,
    stmt: Select[Any],
    page: int,
    per_page: int,
) -> dict[str, Any]:
    """Execute ``stmt`` with offset/limit + a total-count subquery.

    Returns the standard envelope used by all list endpoints.
    """
    page = max(1, page)
    per_page = max(1, min(per_page, MAX_PER_PAGE))

    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = session.execute(stmt.offset((page - 1) * per_page).limit(per_page)).scalars().all()
    pages = (total + per_page - 1) // per_page if per_page else 1

    return {
        "items": rows,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": pages,
            "has_next": page < pages,
            "has_prev": page > 1,
        },
    }
