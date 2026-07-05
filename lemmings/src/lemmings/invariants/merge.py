"""Invariant: merge order respects file conflicts."""

from __future__ import annotations

from collections.abc import Iterable

from lemmings.schemas import TraceEvent


def merge_order_respects_conflicts(events: Iterable[TraceEvent]) -> None:
    """Assert: if two tickets share a file, they never both appear as
    `MERGED` at the same clock time, and a `MERGE_BLOCKED` is only
    cleared in a later cycle.

    We approximate this by checking that whenever `MERGED` fires for
    ticket T, no other `MERGED` event for a ticket T' that shares files
    with T fires at the same clock time.

    File overlap is recovered from `MERGE_PLAN.conflicts` payload.
    """
    merged_at: list[tuple[float, str]] = []
    conflicts: set[tuple[str, str]] = set()
    for ev in events:
        if ev.kind == "MERGE_PLAN":
            for pair in ev.payload.get("conflicts") or ():
                if isinstance(pair, list) and len(pair) == 2:
                    conflicts.add((pair[0], pair[1]))
        elif ev.kind == "MERGED":
            ticket_id = ev.payload.get("ticket_id")
            if isinstance(ticket_id, str):
                merged_at.append((ev.clock, ticket_id))

    by_clock: dict[float, list[str]] = {}
    for clock, tid in merged_at:
        by_clock.setdefault(clock, []).append(tid)
    for clock, ids in by_clock.items():
        for i, a in enumerate(ids):
            for b in ids[i + 1 :]:
                if (a, b) in conflicts or (b, a) in conflicts:
                    raise AssertionError(
                        f"conflicting tickets {a} & {b} both merged at clock={clock}"
                    )
