"""Default Chart of Accounts for a mobile-shop tenant.

Called from the tenant signup flow so every new tenant gets a working ledger
out of the box. The CoA mirrors the legacy app's accounting model (cash,
inventory at cost, AR for debts, owner's drawings separated from operational
expenses) but expressed as proper double-entry accounts.

System-managed accounts carry a ``system_key`` so other services
(sales/expenses/treasury/capital) can resolve them without hardcoding codes:

    CASH, BANK, AR (accounts receivable), AP (accounts payable),
    INVENTORY, SALES_REVENUE, SERVICE_REVENUE, COGS,
    OPERATING_EXPENSES, OWNER_CAPITAL, OWNER_DRAWINGS, RETAINED_EARNINGS

Adding a new system_key here means downstream services can immediately use
it via ``get_system_account(tenant_id, "FOO")``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.modules.accounting.models import Account, AccountType


# --- System keys (canonical names) ------------------------------------------

class SystemAccount:
    CASH = "CASH"
    BANK = "BANK"
    AR = "AR"                    # Accounts Receivable (customer debts)
    AP = "AP"                    # Accounts Payable (supplier debts)
    INVENTORY = "INVENTORY"
    SALES_REVENUE = "SALES_REVENUE"
    SERVICE_REVENUE = "SERVICE_REVENUE"
    SALES_DISCOUNTS = "SALES_DISCOUNTS"
    SALES_RETURNS = "SALES_RETURNS"
    COGS = "COGS"                # Cost of goods sold
    OPERATING_EXPENSES = "OPERATING_EXPENSES"
    SALARIES = "SALARIES"
    RENT = "RENT"
    UTILITIES = "UTILITIES"
    OTHER_EXPENSES = "OTHER_EXPENSES"
    OWNER_CAPITAL = "OWNER_CAPITAL"
    OWNER_DRAWINGS = "OWNER_DRAWINGS"
    RETAINED_EARNINGS = "RETAINED_EARNINGS"


# --- CoA blueprint ----------------------------------------------------------

@dataclass(frozen=True, slots=True)
class _CoaNode:
    code: str
    name: str
    name_ar: str
    type: AccountType
    system_key: Optional[str] = None
    children: tuple["_CoaNode", ...] = ()


_BLUEPRINT: tuple[_CoaNode, ...] = (
    # =========================================================
    # 1xxx — Assets
    # =========================================================
    _CoaNode(
        code="1000", name="Assets", name_ar="الأصول", type=AccountType.asset,
        children=(
            _CoaNode(
                code="1100", name="Current Assets", name_ar="الأصول المتداولة",
                type=AccountType.asset,
                children=(
                    _CoaNode("1110", "Cash on Hand", "النقدية بالصندوق",
                             AccountType.asset, SystemAccount.CASH),
                    _CoaNode("1120", "Bank", "البنك",
                             AccountType.asset, SystemAccount.BANK),
                    _CoaNode("1130", "Accounts Receivable", "الذمم المدينة (العملاء)",
                             AccountType.asset, SystemAccount.AR),
                    _CoaNode("1140", "Inventory", "المخزون (البضاعة)",
                             AccountType.asset, SystemAccount.INVENTORY),
                ),
            ),
        ),
    ),

    # =========================================================
    # 2xxx — Liabilities
    # =========================================================
    _CoaNode(
        code="2000", name="Liabilities", name_ar="الالتزامات",
        type=AccountType.liability,
        children=(
            _CoaNode(
                code="2100", name="Current Liabilities",
                name_ar="الالتزامات المتداولة",
                type=AccountType.liability,
                children=(
                    _CoaNode("2110", "Accounts Payable", "الذمم الدائنة (الموردين)",
                             AccountType.liability, SystemAccount.AP),
                ),
            ),
        ),
    ),

    # =========================================================
    # 3xxx — Equity
    # =========================================================
    _CoaNode(
        code="3000", name="Equity", name_ar="حقوق الملكية",
        type=AccountType.equity,
        children=(
            _CoaNode("3100", "Owner's Capital", "رأس المال",
                     AccountType.equity, SystemAccount.OWNER_CAPITAL),
            _CoaNode("3200", "Owner's Drawings", "مسحوبات المالك",
                     AccountType.equity, SystemAccount.OWNER_DRAWINGS),
            _CoaNode("3300", "Retained Earnings", "الأرباح المحتجزة",
                     AccountType.equity, SystemAccount.RETAINED_EARNINGS),
        ),
    ),

    # =========================================================
    # 4xxx — Revenue
    # =========================================================
    _CoaNode(
        code="4000", name="Revenue", name_ar="الإيرادات",
        type=AccountType.revenue,
        children=(
            _CoaNode("4100", "Sales Revenue", "إيرادات المبيعات",
                     AccountType.revenue, SystemAccount.SALES_REVENUE),
            _CoaNode("4200", "Service Revenue", "إيرادات الصيانة",
                     AccountType.revenue, SystemAccount.SERVICE_REVENUE),
            _CoaNode("4900", "Sales Discounts", "خصم المبيعات",
                     AccountType.revenue, SystemAccount.SALES_DISCOUNTS),
            _CoaNode("4910", "Sales Returns", "مرتجعات المبيعات",
                     AccountType.revenue, SystemAccount.SALES_RETURNS),
        ),
    ),

    # =========================================================
    # 5xxx — Expenses
    # =========================================================
    _CoaNode(
        code="5000", name="Expenses", name_ar="المصروفات",
        type=AccountType.expense,
        children=(
            _CoaNode("5100", "Cost of Goods Sold", "تكلفة البضاعة المباعة",
                     AccountType.expense, SystemAccount.COGS),
            _CoaNode("5200", "Operating Expenses", "المصروفات التشغيلية",
                     AccountType.expense, SystemAccount.OPERATING_EXPENSES),
            _CoaNode("5210", "Salaries", "المرتبات",
                     AccountType.expense, SystemAccount.SALARIES),
            _CoaNode("5220", "Rent", "الإيجار",
                     AccountType.expense, SystemAccount.RENT),
            _CoaNode("5230", "Utilities", "المرافق (كهرباء/مياه/إنترنت)",
                     AccountType.expense, SystemAccount.UTILITIES),
            _CoaNode("5900", "Other Expenses", "مصروفات أخرى",
                     AccountType.expense, SystemAccount.OTHER_EXPENSES),
        ),
    ),
)


def _create_nodes(
    session: Session,
    tenant_id: uuid.UUID,
    nodes: tuple[_CoaNode, ...],
    parent_id: Optional[uuid.UUID] = None,
) -> None:
    for node in nodes:
        acct = Account(
            tenant_id=tenant_id,
            code=node.code,
            name=node.name,
            name_ar=node.name_ar,
            type=node.type,
            parent_id=parent_id,
            system_key=node.system_key,
            is_active=True,
        )
        session.add(acct)
        session.flush()
        if node.children:
            _create_nodes(session, tenant_id, node.children, parent_id=acct.id)


def seed_default_chart(session: Session, tenant_id: uuid.UUID) -> int:
    """Insert the default CoA for a fresh tenant. Returns the row count."""
    before = session.query(Account).count()
    _create_nodes(session, tenant_id, _BLUEPRINT)
    session.flush()
    after = session.query(Account).count()
    return after - before
