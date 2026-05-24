"""Reports HTTP routes.

    GET  /api/v1/reports/dashboard
    GET  /api/v1/reports/pnl?from&to&branch_id
    GET  /api/v1/reports/balance-sheet?as_of
    GET  /api/v1/reports/sales-summary?from&to&branch_id
    GET  /api/v1/reports/inventory-summary?branch_id
    GET  /api/v1/reports/top-products?from&to&limit&branch_id
"""

from __future__ import annotations

import uuid
from datetime import date

from flask import Blueprint, g, request
from werkzeug.exceptions import BadRequest

from app.core.http.responses import ok
from app.core.permissions import require_perm
from app.modules.rbac import Permission
from app.modules.reports import service


reports_bp = Blueprint("reports", __name__, url_prefix="/reports")


def _tenant_id() -> uuid.UUID:
    tid = getattr(g, "tenant_id", None)
    if tid is None:
        raise BadRequest("Tenant context required.")
    return tid


def _parse_date(v, default=None):
    if not v:
        return default
    try:
        return date.fromisoformat(v)
    except ValueError:
        raise BadRequest(f"Invalid date '{v}'.")


def _parse_uuid(v):
    if not v:
        return None
    try:
        return uuid.UUID(v)
    except ValueError:
        raise BadRequest(f"Invalid UUID '{v}'.")


@reports_bp.get("/dashboard")
@require_perm(Permission.REPORTS_FINANCIAL)
def dashboard_route():
    tid = _tenant_id()
    d = service.executive_dashboard(
        tenant_id=tid, branch_id=_parse_uuid(request.args.get("branch_id"))
    )
    return ok({
        "today": d.today.isoformat(),
        "cash_balance": str(d.cash_balance),
        "bank_balance": str(d.bank_balance),
        "ar_total": str(d.ar_total),
        "ap_total": str(d.ap_total),
        "inventory_value": str(d.inventory_value),
        "today_sales": str(d.today_sales),
        "today_invoices": d.today_invoices,
        "today_net_profit": str(d.today_net_profit),
        "month_sales": str(d.month_sales),
        "month_net_profit": str(d.month_net_profit),
        "low_stock_count": d.low_stock_count,
    })


@reports_bp.get("/pnl")
@require_perm(Permission.REPORTS_FINANCIAL)
def pnl_route():
    tid = _tenant_id()
    today = date.today()
    df = _parse_date(request.args.get("from"), default=today.replace(day=1))
    dt = _parse_date(request.args.get("to"), default=today)
    pnl = service.profit_and_loss(
        tenant_id=tid,
        date_from=df, date_to=dt,
        branch_id=_parse_uuid(request.args.get("branch_id")),
    )
    return ok({
        "date_from": pnl.date_from.isoformat(),
        "date_to": pnl.date_to.isoformat(),
        "revenue": [{
            "code": l.code, "name": l.name, "name_ar": l.name_ar,
            "amount": str(l.amount),
        } for l in pnl.revenue_lines],
        "expense": [{
            "code": l.code, "name": l.name, "name_ar": l.name_ar,
            "amount": str(l.amount),
        } for l in pnl.expense_lines],
        "total_revenue": str(pnl.total_revenue),
        "total_expense": str(pnl.total_expense),
        "net_profit": str(pnl.net_profit),
    })


@reports_bp.get("/balance-sheet")
@require_perm(Permission.REPORTS_FINANCIAL)
def balance_sheet_route():
    tid = _tenant_id()
    as_of = _parse_date(request.args.get("as_of"), default=date.today())
    bs = service.balance_sheet(tenant_id=tid, as_of=as_of)
    def lines(rows):
        return [{
            "code": l.code, "name": l.name, "name_ar": l.name_ar,
            "amount": str(l.amount),
        } for l in rows]
    return ok({
        "as_of": bs.as_of.isoformat(),
        "assets": lines(bs.assets),
        "liabilities": lines(bs.liabilities),
        "equity": lines(bs.equity),
        "total_assets": str(bs.total_assets),
        "total_liabilities": str(bs.total_liabilities),
        "total_equity": str(bs.total_equity),
        "is_balanced": bs.is_balanced,
    })


@reports_bp.get("/sales-summary")
@require_perm(Permission.REPORTS_SALES)
def sales_summary_route():
    tid = _tenant_id()
    today = date.today()
    df = _parse_date(request.args.get("from"), default=today.replace(day=1))
    dt = _parse_date(request.args.get("to"), default=today)
    s = service.sales_summary(
        tenant_id=tid, date_from=df, date_to=dt,
        branch_id=_parse_uuid(request.args.get("branch_id")),
    )
    return ok({
        "date_from": s.date_from.isoformat(),
        "date_to": s.date_to.isoformat(),
        "invoice_count": s.invoice_count,
        "gross_revenue": str(s.gross_revenue),
        "discount_total": str(s.discount_total),
        "net_revenue": str(s.net_revenue),
        "cogs_total": str(s.cogs_total),
        "gross_profit": str(s.gross_profit),
        "avg_ticket": str(s.avg_ticket),
    })


@reports_bp.get("/inventory-summary")
@require_perm(Permission.REPORTS_INVENTORY)
def inventory_summary_route():
    tid = _tenant_id()
    s = service.inventory_summary(
        tenant_id=tid, branch_id=_parse_uuid(request.args.get("branch_id"))
    )
    return ok({
        "total_items_on_hand": s.total_items_on_hand,
        "distinct_skus": s.distinct_skus,
        "low_stock_skus": s.low_stock_skus,
        "out_of_stock_skus": s.out_of_stock_skus,
        "total_inventory_value": str(s.total_inventory_value),
        "by_category": {k: str(v) for k, v in s.by_category.items()},
    })


@reports_bp.get("/top-products")
@require_perm(Permission.REPORTS_SALES)
def top_products_route():
    tid = _tenant_id()
    today = date.today()
    df = _parse_date(request.args.get("from"), default=today.replace(day=1))
    dt = _parse_date(request.args.get("to"), default=today)
    try:
        limit = max(1, min(50, int(request.args.get("limit", 10))))
    except (TypeError, ValueError):
        limit = 10
    rows = service.top_products(
        tenant_id=tid, date_from=df, date_to=dt, limit=limit,
        branch_id=_parse_uuid(request.args.get("branch_id")),
    )
    return ok([
        {
            "product_id": str(r.product_id),
            "product_name": r.product_name,
            "qty_sold": r.qty_sold,
            "revenue": str(r.revenue),
            "cogs": str(r.cogs),
            "profit": str(r.profit),
        }
        for r in rows
    ])


@reports_bp.get("/sales-trend")
@require_perm(Permission.REPORTS_SALES)
def sales_trend_route():
    """Daily sales + profit for the last N days (default 30, max 365)."""
    tid = _tenant_id()
    try:
        days = max(1, min(365, int(request.args.get("days", 30))))
    except (TypeError, ValueError):
        days = 30
    points = service.sales_trend(
        tenant_id=tid,
        days=days,
        branch_id=_parse_uuid(request.args.get("branch_id")),
    )
    return ok([
        {
            "date": p.date.isoformat(),
            "sales": str(p.sales),
            "profit": str(p.profit),
            "invoices": p.invoices,
        }
        for p in points
    ])
