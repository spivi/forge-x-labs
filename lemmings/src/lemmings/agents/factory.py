"""Agent factory keyed on `LEMMINGS_MODE`.

v1 only ships sim agents — `LEMMINGS_MODE=real` raises NotImplementedError.
"""

from __future__ import annotations

import os
from random import Random

from lemmings.agents.sim.budget_review import SimBudgetReview
from lemmings.agents.sim.code_reviewer import SimCodeReviewer
from lemmings.agents.sim.developer import SimDeveloper
from lemmings.agents.sim.scrum_master import SimScrumMaster
from lemmings.sim.priors import Priors
from lemmings.sim.trace import Trace
from lemmings.world.protocol import World

ENV_VAR = "LEMMINGS_MODE"


def current_mode() -> str:
    return os.environ.get(ENV_VAR, "sim")


def build_orchestrator(
    rng: Random,
    priors: Priors,
    world: World,
    trace: Trace,
) -> SimScrumMaster:
    mode = current_mode()
    if mode == "sim":
        return SimScrumMaster(rng=rng, priors=priors, world=world, trace=trace)
    if mode == "real":
        raise NotImplementedError("LEMMINGS_MODE=real lands in v2")
    raise ValueError(f"unknown {ENV_VAR}={mode!r}")


def build_budget_review(priors: Priors, tick_interval_min: float = 30.0) -> SimBudgetReview:
    mode = current_mode()
    if mode == "sim":
        return SimBudgetReview(priors=priors, tick_interval_min=tick_interval_min)
    if mode == "real":
        raise NotImplementedError("LEMMINGS_MODE=real lands in v2")
    raise ValueError(f"unknown {ENV_VAR}={mode!r}")


__all__ = [
    "ENV_VAR",
    "build_budget_review",
    "build_orchestrator",
    "current_mode",
    "SimBudgetReview",
    "SimCodeReviewer",
    "SimDeveloper",
    "SimScrumMaster",
]
