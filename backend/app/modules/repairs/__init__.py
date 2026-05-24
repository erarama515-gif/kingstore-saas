"""Repairs module — phone/device maintenance workflow.

Lifecycle: ``received → in_progress → done → delivered``.
On delivery, the service posts the Service Revenue journal entry. The
legacy app collapsed all of this into a single ``Transaction(service)`` row;
we preserve the exact behavior while making each stage observable.
"""

from app.modules.repairs.service import (
    create_ticket,
    update_status,
    deliver,
    get_ticket,
    list_tickets,
)


__all__ = [
    "create_ticket",
    "update_status",
    "deliver",
    "get_ticket",
    "list_tickets",
]
