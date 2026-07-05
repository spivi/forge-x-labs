"""Invariant: tickets that hit the retry cap with FAIL must be escalated."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from lemmings.schemas import TraceEvent


def escalation_when_loop_exhausted(
    events: Iterable[TraceEvent], max_attempts: int = 3
) -> None:
    """Assert: any ticket that reaches `max_attempts` FAIL reviews fires
    an `ESCALATED` event before the trace ends."""
    fails: dict[str, int] = defaultdict(int)
    escalated: set[str] = set()
    for ev in events:
        if ev.kind == "REVIEW_COMPLETED" and ev.payload.get("verdict") == "fail":
            ticket_id = ev.payload.get("ticket_id")
            if isinstance(ticket_id, str):
                fails[ticket_id] += 1
        elif ev.kind == "ESCALATED":
            ticket_id = ev.payload.get("ticket_id")
            if isinstance(ticket_id, str):
                escalated.add(ticket_id)

    for ticket_id, count in fails.items():
        if count >= max_attempts and ticket_id not in escalated:
            raise AssertionError(
                f"ticket {ticket_id} hit {count} FAIL reviews but was not escalated"
            )
