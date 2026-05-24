"""Accounting HTTP routes.

Endpoints (all under ``/api/v1/accounting`` and gated by RBAC):

    GET  /accounts                       — list CoA
    GET  /accounts/{id}/balance          — single account balance
    GET  /accounts/{id}/ledger           — line-level history (paginated)
    POST /journal-entries                — manually post a balanced entry
    POST /journal-entries/{id}/reverse   — reverse a prior entry
    GET  /journal-entries/{id}           — view entry details
    GET  /trial-balance                  — full trial balance with filters
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.core.http.responses import created, ok
from app.core.http.validation import parse_json
from app.core.pagination import paginate_offset, parse_page_args
from app.core.permissions import require_perm
from app.extensions import db
from app.modules.accounting import aging as aging_mod
from app.modules.accounting import repository as repo
from app.modules.accounting import service
from app.modules.accounting.models import Account, JournalEntry, JournalLine
from app.modules.accounting.schemas import (
    AccountResponse,
    JournalEntryCreate,
    JournalEntryResponse,
    JournalLineResponse,
    TrialBalanceResponse,
    TrialBalanceRow,
)
from app.modules.rbac import Permission


accounting_bp = Blueprint("accounting", __name__, url_prefix="/accounting")


# --- Serializers -----------------------------------------------------------

def _account_payload(a: Account) -> dict:
    return AccountResponse(
        id=a.id,
        code=a.code,
        name=a.name,
        name_ar=a.name_ar,
        type=a.type.value,
        parent_id=a.parent_id,
        system_key=a.system_key,
        is_active=a.is_active,
    ).model_dump(mode="json")


def _line_payload(l: JournalLine) -> JournalLineResponse:
    return JournalLineResponse(
        id=l.id,
        account_id=l.account_id,
        debit=l.debit,
        credit=l.credit,
        description=l.description,
    )


def _entry_payload(e: JournalEntry) -> dict:
    return JournalEntryResponse(
        id=e.id,
        entry_date=e.entry_date,
        branch_id=e.branch_id,
        source=e.source,
        source_ref=e.source_ref,
        reference=e.reference,
        description=e.description,
        posted_at=e.posted_at,
        posted_by_id=e.posted_by_id,
        reverses_id=e.reverses_id,
        lines=[_line_payload(l) for l in e.lines],
    ).model_dump(mode="json")


# --- Routes ----------------------------------------------------------------

@accounting_bp.get("/accounts")
@require_perm(Permission.ACCOUNTING_READ)
def list_accounts_route():
    tenant_id = service.current_tenant_required()
    only_active = request.args.get("active", "1") == "1"
    accounts = repo.list_accounts(db.session, tenant_id=tenant_id, only_active=only_active)
    return ok([_account_payload(a) for a in accounts])


@accounting_bp.get("/accounts/<uuid:account_id>/balance")
@require_perm(Permission.ACCOUNTING_READ)
def account_balance_route(account_id: uuid.UUID):
    tenant_id = service.current_tenant_required()
    args = request.args
    bal = service.account_balance(
        tenant_id=tenant_id,
        account_id=account_id,
        date_from=_parse_date(args.get("from")),
        date_to=_parse_date(args.get("to")),
        branch_id=_parse_uuid(args.get("branch_id")),
    )
    return ok({
        "account_id": str(bal.account_id),
        "debit_total": str(bal.debit_total),
        "credit_total": str(bal.credit_total),
        "balance": str(bal.balance),
    })


@accounting_bp.get("/accounts/<uuid:account_id>/ledger")
@require_perm(Permission.ACCOUNTING_READ)
def account_ledger_route(account_id: uuid.UUID):
    tenant_id = service.current_tenant_required()
    pa = parse_page_args()
    from sqlalchemy import select
    stmt = (
        select(JournalLine)
        .where(
            JournalLine.tenant_id == tenant_id,
            JournalLine.account_id == account_id,
        )
        .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
        .order_by(JournalEntry.entry_date.desc(), JournalLine.id.desc())
    )
    page = paginate_offset(db.session, stmt, pa.page, pa.per_page)
    page["items"] = [_line_payload(l).model_dump(mode="json") for l in page["items"]]
    return ok(page["items"], meta={"pagination": page["pagination"]})


@accounting_bp.post("/journal-entries")
@require_perm(Permission.ACCOUNTING_POST)
def post_entry_route():
    tenant_id = service.current_tenant_required()
    payload = parse_json(JournalEntryCreate)
    user_id = _user_uuid(get_jwt_identity())
    entry = service.post_journal_entry(
        tenant_id=tenant_id,
        entry_date=payload.entry_date,
        branch_id=payload.branch_id,
        reference=payload.reference,
        description=payload.description,
        source="manual",
        lines=[
            service.LineInput(
                account_id=l.account_id,
                debit=l.debit,
                credit=l.credit,
                description=l.description,
            )
            for l in payload.lines
        ],
        posted_by_id=user_id,
    )
    db.session.commit()
    return created(_entry_payload(entry))


@accounting_bp.post("/journal-entries/<uuid:entry_id>/reverse")
@require_perm(Permission.ACCOUNTING_POST)
def reverse_entry_route(entry_id: uuid.UUID):
    tenant_id = service.current_tenant_required()
    body = request.get_json(silent=True) or {}
    reason = (body.get("reason") or "").strip()
    if not reason:
        from werkzeug.exceptions import BadRequest
        raise BadRequest("reason is required")
    user_id = _user_uuid(get_jwt_identity())
    reversal = service.reverse_journal_entry(
        tenant_id=tenant_id,
        entry_id=entry_id,
        reason=reason,
        posted_by_id=user_id,
    )
    db.session.commit()
    return created(_entry_payload(reversal))


@accounting_bp.get("/journal-entries/<uuid:entry_id>")
@require_perm(Permission.ACCOUNTING_READ)
def get_entry_route(entry_id: uuid.UUID):
    tenant_id = service.current_tenant_required()
    entry = repo.get_journal_entry(db.session, entry_id)
    if entry is None or entry.tenant_id != tenant_id:
        from werkzeug.exceptions import NotFound
        raise NotFound("Journal entry not found.")
    return ok(_entry_payload(entry))


@accounting_bp.get("/aging/ar")
@require_perm(Permission.REPORTS_FINANCIAL)
def ar_aging_route():
    tenant_id = service.current_tenant_required()
    as_of = _parse_date(request.args.get("as_of"))
    rows = aging_mod.ar_aging(db.session, tenant_id=tenant_id, as_of=as_of)
    return ok([
        {
            "counterparty_id": str(r.counterparty_id),
            "counterparty_name": r.counterparty_name,
            "buckets": {k: str(v) for k, v in r.buckets.items()},
            "total": str(r.total),
        }
        for r in rows
    ])


@accounting_bp.get("/aging/ap")
@require_perm(Permission.REPORTS_FINANCIAL)
def ap_aging_route():
    tenant_id = service.current_tenant_required()
    as_of = _parse_date(request.args.get("as_of"))
    rows = aging_mod.ap_aging(db.session, tenant_id=tenant_id, as_of=as_of)
    return ok([
        {
            "counterparty_id": str(r.counterparty_id),
            "counterparty_name": r.counterparty_name,
            "buckets": {k: str(v) for k, v in r.buckets.items()},
            "total": str(r.total),
        }
        for r in rows
    ])


@accounting_bp.get("/trial-balance")
@require_perm(Permission.REPORTS_FINANCIAL)
def trial_balance_route():
    tenant_id = service.current_tenant_required()
    args = request.args
    report = service.trial_balance(
        tenant_id=tenant_id,
        branch_id=_parse_uuid(args.get("branch_id")),
        date_from=_parse_date(args.get("from")),
        date_to=_parse_date(args.get("to")),
    )
    body = TrialBalanceResponse(
        rows=[
            TrialBalanceRow(
                account_id=l.account.id,
                code=l.account.code,
                name=l.account.name,
                name_ar=l.account.name_ar,
                type=l.account.type.value,
                debit_total=l.debit_total,
                credit_total=l.credit_total,
                balance=l.balance,
            )
            for l in report.lines
        ],
        debit_grand_total=report.debit_grand_total,
        credit_grand_total=report.credit_grand_total,
        is_balanced=report.is_balanced,
    )
    return ok(body.model_dump(mode="json"))


# --- Local helpers ---------------------------------------------------------

def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        from werkzeug.exceptions import BadRequest
        raise BadRequest(f"Invalid date '{value}', expected YYYY-MM-DD.") from exc


def _parse_uuid(value: str | None) -> uuid.UUID | None:
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        from werkzeug.exceptions import BadRequest
        raise BadRequest(f"Invalid UUID '{value}'.") from exc


def _user_uuid(identity: str | None) -> uuid.UUID | None:
    if not identity:
        return None
    try:
        return uuid.UUID(identity)
    except ValueError:
        return None


@accounting_bp.get("/activity")
@require_perm(Permission.ACCOUNTING_READ)
def activity_route():
    """Recent journal-entry activity feed.

    Returns the latest N entries (default 50, max 200) for the tenant,
    optionally filtered by ``source`` (sale|purchase|expense|capital|...) and
    ``branch_id``. Powers the dashboard activity panel and the /activity page.
    """
    tenant_id = service.current_tenant_required()
    from sqlalchemy import select
    try:
        limit = max(1, min(200, int(request.args.get("limit", 50))))
    except (TypeError, ValueError):
        limit = 50
    src_filter = (request.args.get("source") or "").strip() or None
    branch = _parse_uuid(request.args.get("branch_id"))

    stmt = (
        select(JournalEntry)
        .where(JournalEntry.tenant_id == tenant_id)
        .order_by(JournalEntry.posted_at.desc())
        .limit(limit)
    )
    if src_filter:
        stmt = stmt.where(JournalEntry.source == src_filter)
    if branch is not None:
        stmt = stmt.where(JournalEntry.branch_id == branch)

    entries = db.session.execute(stmt).scalars().all()
    return ok([
        {
            "id": str(e.id),
            "entry_date": e.entry_date.isoformat(),
            "posted_at": e.posted_at.isoformat() if e.posted_at else None,
            "source": e.source,
            "source_ref": e.source_ref,
            "reference": e.reference,
            "description": e.description,
            "branch_id": str(e.branch_id) if e.branch_id else None,
            # Compute a single magnitude so the UI can show "amount" even
            # though entries are debit/credit balanced.
            "amount": str(sum((l.debit for l in e.lines), Decimal("0"))),
        }
        for e in entries
    ])
