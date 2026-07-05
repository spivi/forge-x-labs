"""Budget gate decision logic.

Extracted from `.dev-context/agents/scrum_master.md` §1b. Pure function
of World state; testable with no markdown round-trip.
"""

from __future__ import annotations

from dataclasses import dataclass

from lemmings.world.protocol import World


@dataclass(frozen=True)
class BudgetDecision:
    allow: bool
    reason: str
    spent_usd: float
    budget_usd: float
    hard_cap_usd: float


def evaluate_budget(world: World, hard_cap_factor: float = 1.2) -> BudgetDecision:
    """Decide whether more agents may be spawned.

    Returns `allow=False` once cumulative spend exceeds the hard cap, or
    once the world has been explicitly budget-locked (e.g. by a chaos
    disruptor).
    """
    spent = world.total_billed_usd()
    budget = world.sprint_budget_usd()
    hard_cap = budget * hard_cap_factor

    if world.is_budget_locked():
        return BudgetDecision(
            allow=False,
            reason="budget_locked",
            spent_usd=spent,
            budget_usd=budget,
            hard_cap_usd=hard_cap,
        )
    if spent >= hard_cap:
        return BudgetDecision(
            allow=False,
            reason="hard_cap_exceeded",
            spent_usd=spent,
            budget_usd=budget,
            hard_cap_usd=hard_cap,
        )
    return BudgetDecision(
        allow=True,
        reason="ok",
        spent_usd=spent,
        budget_usd=budget,
        hard_cap_usd=hard_cap,
    )
