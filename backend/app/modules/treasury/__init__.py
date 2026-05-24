"""Treasury module.

The legacy ``close_day`` carried a running cash balance forward by inserting
a special ``opening_balance`` transaction. In a real ledger this is
*unnecessary* — the Cash account balance naturally carries through, and any
historical date's cash position is recoverable by summing journal lines up
to that date.

We still keep a ``DayClose`` table for two reasons:
1. **Discipline**: the cashier explicitly affirms the cash-at-hand at end
   of day; the snapshot becomes the audit anchor.
2. **Demo polish**: shop owners expect a "Close Day" button.
"""

from app.modules.treasury.service import (
    close_day,
    cash_position,
    day_snapshot,
    list_day_closes,
)


__all__ = ["close_day", "cash_position", "day_snapshot", "list_day_closes"]
