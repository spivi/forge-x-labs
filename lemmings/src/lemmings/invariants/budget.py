"""Invariant: no agents are spawned after the budget is exceeded."""

from __future__ import annotations

from collections.abc import Iterable

from lemmings.schemas import TraceEvent

SPAWN_EVENTS = frozenset({"DEVELOPER_STARTED", "REVIEW_STARTED", "TICKET_ASSIGNED"})


def no_agents_after_budget_exceeded(events: Iterable[TraceEvent]) -> None:
    """Assert: once `BUDGET_EXCEEDED` fires, no further spawn events occur."""
    events_list = list(events)
    seen_exceeded_at: float | None = None
    for ev in events_list:
        if ev.kind == "BUDGET_EXCEEDED" and seen_exceeded_at is None:
            seen_exceeded_at = ev.clock
            continue
        if seen_exceeded_at is not None and ev.kind in SPAWN_EVENTS:
            raise AssertionError(
                f"agent spawned at clock={ev.clock} after BUDGET_EXCEEDED at "
                f"clock={seen_exceeded_at}: {ev.kind} {ev.payload}"
            )
