"""Accounting module — the double-entry ledger.

This is the *only* place in the system that writes to ``journal_entries`` and
``journal_lines``. Every other module (sales, expenses, repairs, treasury,
capital) emits accounting facts through ``service.post_journal_entry``.

Money is always ``Decimal`` (or ``Numeric(14, 2)`` in the DB). Never float —
binary float math silently breaks balance sums by sub-cent rounding.

Posted entries are immutable. Corrections are made by posting a *reversal*
entry referencing the original. This preserves a tamper-evident audit trail
that any auditor can reconcile.
"""

from app.modules.accounting.service import (
    post_journal_entry,
    reverse_journal_entry,
    account_balance,
    trial_balance,
)
from app.modules.accounting.coa_seed import seed_default_chart


__all__ = [
    "post_journal_entry",
    "reverse_journal_entry",
    "account_balance",
    "trial_balance",
    "seed_default_chart",
]
