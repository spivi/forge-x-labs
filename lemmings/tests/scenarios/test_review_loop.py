"""Scenario test: review_loop across multiple seeds."""

from __future__ import annotations

import pytest

from lemmings.invariants.escalation import escalation_when_loop_exhausted
from lemmings.invariants.ledger import ledger_monotonic
from lemmings.invariants.retry import retries_capped
from lemmings.scenarios.review_loop import build
from lemmings.sim.scenario import run_scenario

SEEDS = [1, 7, 42, 101, 999]


@pytest.mark.parametrize("seed", SEEDS)
def test_review_loop_invariants(seed: int) -> None:
    scenario = build()
    result = run_scenario(scenario, seed=seed)
    events = list(result.trace.events())

    retries_capped(events, max_attempts=scenario.priors.retry.max_attempts)  # type: ignore[union-attr]
    escalation_when_loop_exhausted(
        events, max_attempts=scenario.priors.retry.max_attempts  # type: ignore[union-attr]
    )
    ledger_monotonic(list(result.world.ledger_rows()))


@pytest.mark.parametrize("seed", SEEDS)
def test_review_loop_actually_escalates(seed: int) -> None:
    """The whole point of this scenario: it must reach ESCALATED."""
    result = run_scenario(build(), seed=seed)
    kinds = [ev.kind for ev in result.trace.events()]
    assert "ESCALATED" in kinds, f"seed={seed} did not escalate; kinds={set(kinds)}"
