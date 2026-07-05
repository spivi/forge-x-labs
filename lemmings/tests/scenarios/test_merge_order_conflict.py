"""Scenario test: merge_order_conflict across multiple seeds."""

from __future__ import annotations

import pytest

from lemmings.invariants.ledger import ledger_monotonic
from lemmings.invariants.merge import merge_order_respects_conflicts
from lemmings.scenarios.merge_order_conflict import build
from lemmings.sim.scenario import run_scenario

SEEDS = [1, 7, 42, 101, 999]


@pytest.mark.parametrize("seed", SEEDS)
def test_merge_order_invariants(seed: int) -> None:
    result = run_scenario(build(), seed=seed)
    events = list(result.trace.events())
    merge_order_respects_conflicts(events)
    ledger_monotonic(list(result.world.ledger_rows()))


@pytest.mark.parametrize("seed", SEEDS)
def test_conflict_detected_in_plan(seed: int) -> None:
    """The two backlog tickets share auth.py — at least one MERGE_PLAN
    should report them as conflicting."""
    result = run_scenario(build(), seed=seed)
    found = False
    for ev in result.trace.events("MERGE_PLAN"):
        for pair in ev.payload.get("conflicts") or ():  # type: ignore[union-attr]
            if isinstance(pair, list) and {"LEM-21", "LEM-22"} == set(pair):
                found = True
                break
        if found:
            break
    assert found, f"seed={seed} never detected the LEM-21/22 conflict"
