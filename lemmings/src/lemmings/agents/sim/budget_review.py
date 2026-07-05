"""SimBudgetReview — periodic watchdog that locks the budget when exhausted.

Self-reschedules every `tick_interval_min`. When cumulative spend
exceeds `sprint_budget · hard_cap_factor`, locks the world's budget;
the orchestrator's budget gate then halts new dispatches.
"""

from __future__ import annotations

from collections.abc import Callable

from lemmings.schemas import AgentKind
from lemmings.sim.des import Clock
from lemmings.sim.priors import Priors
from lemmings.sim.trace import Trace
from lemmings.world.protocol import World


class SimBudgetReview:
    kind = AgentKind.BUDGET_REVIEW

    def __init__(self, priors: Priors, tick_interval_min: float = 30.0) -> None:
        self.priors = priors
        self.tick_interval_min = tick_interval_min

    def schedule_first(self, clock: Clock, world: World, trace: Trace) -> None:
        clock.schedule(self.tick_interval_min, self._tick(world, trace), label="budget_tick")

    def _tick(self, world: World, trace: Trace) -> Callable[[Clock], None]:
        def fn(clock: Clock) -> None:
            spent = world.total_billed_usd()
            budget = world.sprint_budget_usd()
            hard_cap = budget * self.priors.budget.hard_cap_factor
            trace.record(
                clock.now,
                "BUDGET_REVIEW_TICK",
                spent=spent,
                budget=budget,
                hard_cap=hard_cap,
            )
            if spent >= hard_cap and not world.is_budget_locked():
                world.lock_budget(reason="hard_cap_exceeded")
                trace.record(
                    clock.now,
                    "BUDGET_LOCKED",
                    spent=spent,
                    hard_cap=hard_cap,
                )
                return  # do not reschedule; we're done
            clock.schedule(self.tick_interval_min, fn, label="budget_tick")

        return fn
