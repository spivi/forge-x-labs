"""Scenario test: budget_exhausted across multiple seeds."""

from __future__ import annotations

import pytest

from lemmings.invariants.budget import no_agents_after_budget_exceeded
from lemmings.invariants.ledger import ledger_monotonic
from lemmings.scenarios.budget_exhausted import build
from lemmings.sim.scenario import run_scenario

SEEDS = [1, 7, 42, 101, 999]


@pytest.mark.parametrize("seed", SEEDS)
def test_budget_exhausted_invariants(seed: int) -> None:
    result = run_scenario(build(), seed=seed)
    no_agents_after_budget_exceeded(list(result.trace.events()))
    ledger_monotonic(list(result.world.ledger_rows()))


@pytest.mark.parametrize("seed", SEEDS)
def test_budget_eventually_exceeded(seed: int) -> None:
    result = run_scenario(build(), seed=seed)
    kinds = {ev.kind for ev in result.trace.events()}
    # given the tiny budget (2 USD) vs developer cost rate, this should
    # always trip — either via the gate or the budget review watchdog
    assert "BUDGET_EXCEEDED" in kinds or "BUDGET_LOCKED" in kinds, (
        f"seed={seed} did not trip budget; events: {kinds}"
    )
