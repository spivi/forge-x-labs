"""Invariant: review attempts are capped at `max_attempts`."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from lemmings.schemas import TraceEvent


def retries_capped(events: Iterable[TraceEvent], max_attempts: int = 3) -> None:
    """Assert: no ticket sees more than `max_attempts` REVIEW_COMPLETED events."""
    counts: Counter[str] = Counter()
    for ev in events:
        if ev.kind != "REVIEW_COMPLETED":
            continue
        ticket_id = ev.payload.get("ticket_id")
        if not isinstance(ticket_id, str):
            raise AssertionError(f"REVIEW_COMPLETED missing ticket_id: {ev.payload}")
        counts[ticket_id] += 1
        if counts[ticket_id] > max_attempts:
            raise AssertionError(
                f"ticket {ticket_id} reviewed {counts[ticket_id]} times "
                f"(max_attempts={max_attempts})"
            )
