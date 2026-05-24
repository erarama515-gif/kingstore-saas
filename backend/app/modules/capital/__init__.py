"""Capital module — owner's equity movements.

* ``cap_in``  — owner injects cash:   DR Cash / CR Owner's Capital
* ``cap_out`` — owner takes cash out: DR Owner's Drawings / CR Cash
* No new tables: every capital movement is a journal entry with
  ``source = "capital"``. Reports/UI query the ledger directly.
"""

from app.modules.capital.service import (
    capital_inject,
    capital_withdraw,
    list_capital_movements,
    capital_summary,
)


__all__ = [
    "capital_inject",
    "capital_withdraw",
    "list_capital_movements",
    "capital_summary",
]
