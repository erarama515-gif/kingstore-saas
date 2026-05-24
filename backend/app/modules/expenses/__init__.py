"""Expenses module — operational outflows other than COGS.

Every expense posts ``DR <expense_account> / CR Cash`` (or Bank). The
expense_account_key parameter lets the cashier choose which expense bucket
to charge (rent, salaries, utilities, other) — corresponds to the
``5xxx`` accounts seeded into the chart.
"""

from app.modules.expenses.service import (
    create_expense,
    get_expense,
    list_expenses,
    void_expense,
)


__all__ = ["create_expense", "get_expense", "list_expenses", "void_expense"]
