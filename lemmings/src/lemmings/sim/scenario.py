"""Scenario framework — a "level" the simulator runs.

Each scenario provides three injection hooks:

- `initial_backlog`     — tickets to insert at sprint start
- `pre_run_events`      — disruptors at specific clock times
- `output_overrides`    — pin specific RV samples to deterministic values
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from random import Random

from lemmings.agents.factory import build_budget_review, build_orchestrator
from lemmings.schemas import Ticket
from lemmings.sim.des import Clock
from lemmings.sim.priors import Priors, load_default_priors
from lemmings.sim.trace import Trace
from lemmings.world.protocol import World
from lemmings.world.sim import SimWorld

PreRunEvent = tuple[float, Callable[[Clock, World, Trace], None]]


@dataclass
class Scenario:
    name: str
    initial_backlog: list[Ticket] = field(default_factory=list)
    pre_run_events: list[PreRunEvent] = field(default_factory=list)
    sprint_budget_usd: float = 50.0
    budget_review_interval_min: float = 30.0
    run_until_min: float | None = 60 * 24  # 24h cap
    priors: Priors | None = None  # if set, overrides defaults

    def build_world(self) -> SimWorld:
        world = SimWorld(sprint_budget_usd=self.sprint_budget_usd)
        for t in self.initial_backlog:
            world.add_ticket(t)
        return world


@dataclass
class ScenarioResult:
    world: SimWorld
    trace: Trace
    clock: Clock


def run_scenario(
    scenario: Scenario,
    seed: int,
    priors: Priors | None = None,
    trace: Trace | None = None,
) -> ScenarioResult:
    """Execute `scenario` deterministically given `seed`."""
    if priors is None:
        priors = scenario.priors if scenario.priors is not None else load_default_priors()
    if trace is None:
        trace = Trace()

    rng = Random(seed)
    world = scenario.build_world()
    clock = Clock()
    clock.metadata["scenario"] = scenario.name
    clock.metadata["seed"] = seed

    # Schedule disruptors before agents start so events at clock=0 are picked up.
    for at, hook in scenario.pre_run_events:
        clock.schedule_at(at, lambda c, h=hook, w=world, t=trace: h(c, w, t), label="disruptor")

    orchestrator = build_orchestrator(rng=rng, priors=priors, world=world, trace=trace)
    budget_review = build_budget_review(
        priors=priors, tick_interval_min=scenario.budget_review_interval_min
    )
    budget_review.schedule_first(clock, world, trace)

    # Kickoff at clock=0
    orchestrator.kickoff(clock)

    clock.run(until=scenario.run_until_min)
    trace.record(clock.now, "SPRINT_ENDED", pending_events=clock.pending())

    return ScenarioResult(world=world, trace=trace, clock=clock)
