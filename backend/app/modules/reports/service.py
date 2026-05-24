"""Financial + operational reports.

Everything here is read-only and computes its result from the existing
tables — no separate reporting store.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date as date_t, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, select

from app.extensions import db
from app.modules.accounting.coa_seed import SystemAccount
from app.modules.accounting.models import Account, AccountType, JournalEntry, JournalLine
from app.modules.accounting.repository import get_system_account
from app.modules.inventory.models import StockLevel
from app.modules.products.models import Product
from app.modules.sales.models import Sale, SaleLine


# --- Profit & Loss --------------------------------------------------------

@dataclass(frozen=True, slots=True)
class AccountLine:
    code: str
    name: str
    name_ar: Optional[str]
    amount: Decimal


@dataclass(frozen=True, slots=True)
class PnLReport:
    date_from: date_t
    date_to: date_t
    revenue_lines: list[AccountLine]
    expense_lines: list[AccountLine]
    total_revenue: Decimal
    total_expense: Decimal
    net_profit: Decimal


def profit_and_loss(
    *,
    tenant_id: uuid.UUID,
    date_from: date_t,
    date_to: date_t,
    branch_id: Optional[uuid.UUID] = None,
) -> PnLReport:
    session = db.session

    def section(type_: AccountType) -> list[AccountLine]:
        stmt = (
            select(
                Account,
                func.coalesce(func.sum(JournalLine.debit), 0),
                func.coalesce(func.sum(JournalLine.credit), 0),
            )
            .select_from(Account)
            .join(JournalLine, JournalLine.account_id == Account.id)
            .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
            .where(
                Account.tenant_id == tenant_id,
                Account.type == type_,
                JournalEntry.entry_date >= date_from,
                JournalEntry.entry_date <= date_to,
            )
            .group_by(Account.id)
            .order_by(Account.code)
        )
        if branch_id is not None:
            stmt = stmt.where(JournalEntry.branch_id == branch_id)
        rows = session.execute(stmt).all()
        out: list[AccountLine] = []
        for a, dr, cr in rows:
            if type_ == AccountType.revenue:
                amt = (Decimal(cr) - Decimal(dr))
            else:  # expense
                amt = (Decimal(dr) - Decimal(cr))
            if amt != 0:
                out.append(AccountLine(
                    code=a.code, name=a.name, name_ar=a.name_ar,
                    amount=amt.quantize(Decimal("0.01")),
                ))
        return out

    revenue = section(AccountType.revenue)
    expense = section(AccountType.expense)
    total_rev = sum((l.amount for l in revenue), Decimal("0"))
    total_exp = sum((l.amount for l in expense), Decimal("0"))

    return PnLReport(
        date_from=date_from,
        date_to=date_to,
        revenue_lines=revenue,
        expense_lines=expense,
        total_revenue=total_rev,
        total_expense=total_exp,
        net_profit=(total_rev - total_exp).quantize(Decimal("0.01")),
    )


# --- Balance Sheet --------------------------------------------------------

@dataclass(frozen=True, slots=True)
class BalanceSheet:
    as_of: date_t
    assets: list[AccountLine]
    liabilities: list[AccountLine]
    equity: list[AccountLine]
    total_assets: Decimal
    total_liabilities: Decimal
    total_equity: Decimal
    is_balanced: bool


def balance_sheet(
    *, tenant_id: uuid.UUID, as_of: Optional[date_t] = None
) -> BalanceSheet:
    bd = as_of or date_t.today()
    session = db.session

    def section(type_: AccountType) -> list[AccountLine]:
        stmt = (
            select(
                Account,
                func.coalesce(func.sum(JournalLine.debit), 0),
                func.coalesce(func.sum(JournalLine.credit), 0),
            )
            .select_from(Account)
            .join(JournalLine, JournalLine.account_id == Account.id)
            .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
            .where(
                Account.tenant_id == tenant_id,
                Account.type == type_,
                JournalEntry.entry_date <= bd,
            )
            .group_by(Account.id)
            .order_by(Account.code)
        )
        rows = session.execute(stmt).all()
        out: list[AccountLine] = []
        for a, dr, cr in rows:
            if type_ == AccountType.asset:
                amt = Decimal(dr) - Decimal(cr)
            else:
                amt = Decimal(cr) - Decimal(dr)
            if amt != 0:
                out.append(AccountLine(
                    code=a.code, name=a.name, name_ar=a.name_ar,
                    amount=amt.quantize(Decimal("0.01")),
                ))
        return out

    assets = section(AccountType.asset)
    liabilities = section(AccountType.liability)
    equity = section(AccountType.equity)

    # Retained earnings (current period net profit accumulates here at YE)
    # is computed live so the equation balances on any date.
    pnl = profit_and_loss(
        tenant_id=tenant_id,
        date_from=date_t(bd.year, 1, 1),
        date_to=bd,
    )
    if pnl.net_profit != 0:
        equity.append(AccountLine(
            code="(P&L)",
            name="Current Period P&L",
            name_ar="ربح/خسارة الفترة الحالية",
            amount=pnl.net_profit,
        ))

    total_a = sum((l.amount for l in assets), Decimal("0"))
    total_l = sum((l.amount for l in liabilities), Decimal("0"))
    total_e = sum((l.amount for l in equity), Decimal("0"))

    return BalanceSheet(
        as_of=bd,
        assets=assets,
        liabilities=liabilities,
        equity=equity,
        total_assets=total_a,
        total_liabilities=total_l,
        total_equity=total_e,
        is_balanced=(total_a == total_l + total_e),
    )


# --- Sales summary --------------------------------------------------------

@dataclass(frozen=True, slots=True)
class SalesSummary:
    date_from: date_t
    date_to: date_t
    invoice_count: int
    gross_revenue: Decimal
    discount_total: Decimal
    net_revenue: Decimal
    cogs_total: Decimal
    gross_profit: Decimal
    avg_ticket: Decimal


def sales_summary(
    *,
    tenant_id: uuid.UUID,
    date_from: date_t,
    date_to: date_t,
    branch_id: Optional[uuid.UUID] = None,
) -> SalesSummary:
    session = db.session
    stmt = (
        select(
            func.count(Sale.id),
            func.coalesce(func.sum(Sale.subtotal), 0),
            func.coalesce(func.sum(Sale.discount_total), 0),
            func.coalesce(func.sum(Sale.total), 0),
        )
        .where(
            Sale.tenant_id == tenant_id,
            Sale.deleted_at.is_(None),
            Sale.sale_date >= date_from,
            Sale.sale_date <= date_to,
        )
    )
    if branch_id is not None:
        stmt = stmt.where(Sale.branch_id == branch_id)
    cnt, gross, disc, net = session.execute(stmt).one()

    # COGS = sum(line.qty * cost_snapshot) for inventoried lines
    cogs_stmt = (
        select(
            func.coalesce(
                func.sum(SaleLine.qty * SaleLine.cost_snapshot), 0
            )
        )
        .select_from(SaleLine)
        .join(Sale, Sale.id == SaleLine.sale_id)
        .where(
            Sale.tenant_id == tenant_id,
            Sale.deleted_at.is_(None),
            Sale.sale_date >= date_from,
            Sale.sale_date <= date_to,
            SaleLine.is_service.is_(False),
        )
    )
    if branch_id is not None:
        cogs_stmt = cogs_stmt.where(Sale.branch_id == branch_id)
    cogs = session.execute(cogs_stmt).scalar_one()

    net = Decimal(net)
    cogs = Decimal(cogs).quantize(Decimal("0.01"))
    gross_profit = (net - cogs).quantize(Decimal("0.01"))
    avg = (net / cnt).quantize(Decimal("0.01")) if cnt else Decimal("0.00")

    return SalesSummary(
        date_from=date_from,
        date_to=date_to,
        invoice_count=int(cnt),
        gross_revenue=Decimal(gross).quantize(Decimal("0.01")),
        discount_total=Decimal(disc).quantize(Decimal("0.01")),
        net_revenue=net.quantize(Decimal("0.01")),
        cogs_total=cogs,
        gross_profit=gross_profit,
        avg_ticket=avg,
    )


# --- Inventory summary ----------------------------------------------------

@dataclass(frozen=True, slots=True)
class InventorySummary:
    total_items_on_hand: int
    distinct_skus: int
    low_stock_skus: int
    out_of_stock_skus: int
    total_inventory_value: Decimal
    by_category: dict[str, Decimal]


def inventory_summary(
    *, tenant_id: uuid.UUID, branch_id: Optional[uuid.UUID] = None
) -> InventorySummary:
    session = db.session
    # Total items on hand + SKU counts
    base = (
        select(
            func.coalesce(func.sum(StockLevel.qty_on_hand), 0),
            func.count(StockLevel.id),
        )
        .select_from(StockLevel)
        .join(Product, Product.id == StockLevel.product_id)
        .where(StockLevel.tenant_id == tenant_id, Product.deleted_at.is_(None))
    )
    if branch_id is not None:
        base = base.where(StockLevel.branch_id == branch_id)
    total_qty, distinct_skus = session.execute(base).one()

    # Low / out of stock counts
    low_stmt = (
        select(func.count(StockLevel.id))
        .select_from(StockLevel)
        .join(Product, Product.id == StockLevel.product_id)
        .where(
            StockLevel.tenant_id == tenant_id,
            Product.deleted_at.is_(None),
            StockLevel.qty_on_hand > 0,
            StockLevel.qty_on_hand <= Product.reorder_point,
        )
    )
    out_stmt = (
        select(func.count(StockLevel.id))
        .select_from(StockLevel)
        .join(Product, Product.id == StockLevel.product_id)
        .where(
            StockLevel.tenant_id == tenant_id,
            Product.deleted_at.is_(None),
            StockLevel.qty_on_hand == 0,
        )
    )
    if branch_id is not None:
        low_stmt = low_stmt.where(StockLevel.branch_id == branch_id)
        out_stmt = out_stmt.where(StockLevel.branch_id == branch_id)
    low = session.execute(low_stmt).scalar_one()
    out = session.execute(out_stmt).scalar_one()

    # Total value @ cost (using Product.cost)
    val_stmt = (
        select(func.coalesce(func.sum(StockLevel.qty_on_hand * Product.cost), 0))
        .select_from(StockLevel)
        .join(Product, Product.id == StockLevel.product_id)
        .where(StockLevel.tenant_id == tenant_id, Product.deleted_at.is_(None))
    )
    if branch_id is not None:
        val_stmt = val_stmt.where(StockLevel.branch_id == branch_id)
    total_value = Decimal(session.execute(val_stmt).scalar_one()).quantize(Decimal("0.01"))

    # By category
    cat_stmt = (
        select(
            Product.category,
            func.coalesce(func.sum(StockLevel.qty_on_hand * Product.cost), 0),
        )
        .select_from(StockLevel)
        .join(Product, Product.id == StockLevel.product_id)
        .where(StockLevel.tenant_id == tenant_id, Product.deleted_at.is_(None))
        .group_by(Product.category)
    )
    if branch_id is not None:
        cat_stmt = cat_stmt.where(StockLevel.branch_id == branch_id)
    by_cat = {
        c.value: Decimal(v).quantize(Decimal("0.01"))
        for c, v in session.execute(cat_stmt).all()
    }

    return InventorySummary(
        total_items_on_hand=int(total_qty),
        distinct_skus=int(distinct_skus),
        low_stock_skus=int(low),
        out_of_stock_skus=int(out),
        total_inventory_value=total_value,
        by_category=by_cat,
    )


# --- Executive dashboard --------------------------------------------------

@dataclass(frozen=True, slots=True)
class ExecutiveDashboard:
    today: date_t
    cash_balance: Decimal
    bank_balance: Decimal
    ar_total: Decimal
    ap_total: Decimal
    inventory_value: Decimal
    today_sales: Decimal
    today_invoices: int
    today_net_profit: Decimal
    month_sales: Decimal
    month_net_profit: Decimal
    low_stock_count: int


def executive_dashboard(
    *, tenant_id: uuid.UUID, branch_id: Optional[uuid.UUID] = None
) -> ExecutiveDashboard:
    from app.modules.accounting import service as acct

    today = date_t.today()
    first_of_month = today.replace(day=1)

    def bal(key: str) -> Decimal:
        try:
            aid = acct.get_system_account_id(tenant_id, key)
        except Exception:
            return Decimal("0")
        return acct.account_balance(tenant_id=tenant_id, account_id=aid, branch_id=branch_id).balance

    cash = bal(SystemAccount.CASH)
    bank = bal(SystemAccount.BANK)
    ar = bal(SystemAccount.AR)
    ap = bal(SystemAccount.AP)
    inv = bal(SystemAccount.INVENTORY)

    today_pnl = profit_and_loss(
        tenant_id=tenant_id, date_from=today, date_to=today, branch_id=branch_id
    )
    month_pnl = profit_and_loss(
        tenant_id=tenant_id, date_from=first_of_month, date_to=today, branch_id=branch_id
    )
    today_s = sales_summary(
        tenant_id=tenant_id, date_from=today, date_to=today, branch_id=branch_id
    )
    month_s = sales_summary(
        tenant_id=tenant_id, date_from=first_of_month, date_to=today, branch_id=branch_id
    )
    inv_s = inventory_summary(tenant_id=tenant_id, branch_id=branch_id)

    return ExecutiveDashboard(
        today=today,
        cash_balance=cash,
        bank_balance=bank,
        ar_total=ar,
        ap_total=ap,
        inventory_value=inv,
        today_sales=today_s.net_revenue,
        today_invoices=today_s.invoice_count,
        today_net_profit=today_pnl.net_profit,
        month_sales=month_s.net_revenue,
        month_net_profit=month_pnl.net_profit,
        low_stock_count=inv_s.low_stock_skus,
    )


# --- Sales by product (top sellers) --------------------------------------

@dataclass(frozen=True, slots=True)
class TopProduct:
    product_id: uuid.UUID
    product_name: str
    qty_sold: int
    revenue: Decimal
    cogs: Decimal
    profit: Decimal


def top_products(
    *,
    tenant_id: uuid.UUID,
    date_from: date_t,
    date_to: date_t,
    branch_id: Optional[uuid.UUID] = None,
    limit: int = 10,
) -> list[TopProduct]:
    session = db.session
    stmt = (
        select(
            SaleLine.product_id,
            func.coalesce(func.sum(SaleLine.qty), 0),
            func.coalesce(func.sum(SaleLine.line_total), 0),
            func.coalesce(func.sum(SaleLine.qty * SaleLine.cost_snapshot), 0),
        )
        .select_from(SaleLine)
        .join(Sale, Sale.id == SaleLine.sale_id)
        .where(
            Sale.tenant_id == tenant_id,
            Sale.deleted_at.is_(None),
            SaleLine.product_id.is_not(None),
            Sale.sale_date >= date_from,
            Sale.sale_date <= date_to,
        )
        .group_by(SaleLine.product_id)
        .order_by(func.sum(SaleLine.line_total).desc())
        .limit(limit)
    )
    if branch_id is not None:
        stmt = stmt.where(Sale.branch_id == branch_id)
    rows = session.execute(stmt).all()

    # Resolve names in one query
    ids = [r[0] for r in rows]
    name_map: dict[uuid.UUID, str] = {}
    if ids:
        for p in session.execute(
            select(Product.id, Product.name).where(
                Product.tenant_id == tenant_id, Product.id.in_(ids)
            )
        ).all():
            name_map[p[0]] = p[1]

    out: list[TopProduct] = []
    for pid, qty, rev, cogs in rows:
        out.append(TopProduct(
            product_id=pid,
            product_name=name_map.get(pid, "(deleted)"),
            qty_sold=int(qty),
            revenue=Decimal(rev).quantize(Decimal("0.01")),
            cogs=Decimal(cogs).quantize(Decimal("0.01")),
            profit=(Decimal(rev) - Decimal(cogs)).quantize(Decimal("0.01")),
        ))
    return out
