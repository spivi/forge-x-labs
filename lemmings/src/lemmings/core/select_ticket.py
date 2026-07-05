"""Ticket selection — Scrum Master picks the next ticket.

v1: simple FIFO by `id` over backlog tickets. Sufficient to validate
orchestration paths; richer policies (priority, risk-class weighting)
land in v2.
"""

from __future__ import annotations

from lemmings.schemas import Ticket, TicketStatus
from lemmings.world.protocol import World


def select_next_ticket(world: World) -> Ticket | None:
    """Return the next backlog ticket, or `None` if backlog is empty."""
    backlog = world.list_tickets(status=TicketStatus.BACKLOG)
    if not backlog:
        return None
    return min(backlog, key=lambda t: t.id)
