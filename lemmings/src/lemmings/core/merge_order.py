"""Merge ordering decision logic.

Extracted from `.dev-context/rules/parallel-dev.md` "Merge Ordering".
Concurrent PRs that touch overlapping files cannot merge in parallel —
they must serialize. The decision returns a topological merge order
based on file overlap and arrival time (FIFO break ties).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from lemmings.schemas import PR


@dataclass(frozen=True)
class MergePlan:
    order: tuple[str, ...]
    """Ticket IDs in the order they may safely merge."""
    conflict_pairs: tuple[tuple[str, str], ...]
    """File-overlapping ticket pairs that must serialize."""


def _has_file_overlap(a: PR, b: PR) -> bool:
    return bool(set(a.files_touched) & set(b.files_touched))


def plan_merges(prs: Iterable[PR]) -> MergePlan:
    """Compute a safe merge order.

    Two PRs that overlap on any file MUST NOT be flagged as mergeable
    simultaneously. We return them in arrival order (`opened_at`) — the
    first one merges, the rest wait for the next planning cycle.
    """
    pr_list = sorted(prs, key=lambda p: (p.opened_at, p.ticket_id))

    conflicts: list[tuple[str, str]] = []
    cleared: list[PR] = []

    for pr in pr_list:
        conflicting = [c for c in cleared if _has_file_overlap(c, pr)]
        if conflicting:
            for c in conflicting:
                conflicts.append((c.ticket_id, pr.ticket_id))
            continue
        cleared.append(pr)

    return MergePlan(
        order=tuple(c.ticket_id for c in cleared),
        conflict_pairs=tuple(conflicts),
    )
