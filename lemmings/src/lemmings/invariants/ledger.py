"""Invariant: cost ledger is monotonic non-decreasing."""

from __future__ import annotations

from collections.abc import Iterable

from lemmings.schemas import LedgerRow


def ledger_monotonic(rows: Iterable[LedgerRow]) -> None:
    """Assert: every `compute_cost_usd` is non-negative and the cumulative
    sum is non-decreasing (which is automatic, but we also assert each
    individual row is non-negative)."""
    cum = 0.0
    for i, row in enumerate(rows):
        if row.compute_cost_usd < 0:
            raise AssertionError(
                f"ledger row {i} has negative compute_cost_usd={row.compute_cost_usd}"
            )
        cum += row.compute_cost_usd
        if cum < 0:
            raise AssertionError(f"ledger cumulative sum went negative at row {i}: {cum}")
