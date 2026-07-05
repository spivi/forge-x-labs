"""Level: throughput optimum — independent tickets that should merge.

No disruptors, default priors, three small unrelated tickets touching
disjoint files. Used to study tickets-merged-per-dollar across knob
ranges where the orchestrator is *not* engineered to fail.
"""

from __future__ import annotations

from lemmings.schemas import RiskClass, Ticket
from lemmings.sim.scenario import Scenario


def build() -> Scenario:
    return Scenario(
        name="happy_path",
        sprint_budget_usd=200.0,
        budget_review_interval_min=30.0,
        run_until_min=60 * 8,
        initial_backlog=[
            Ticket(
                id="LEM-30",
                title="add /healthz endpoint",
                risk_class=RiskClass.GENERIC,
                complexity=0.7,
                novelty=0.3,
                lines_planned=60,
                files_planned=("health.py",),
            ),
            Ticket(
                id="LEM-31",
                title="format log timestamps",
                risk_class=RiskClass.GENERIC,
                complexity=0.6,
                novelty=0.2,
                lines_planned=40,
                files_planned=("logging_utils.py",),
            ),
            Ticket(
                id="LEM-32",
                title="cache config loader",
                risk_class=RiskClass.GENERIC,
                complexity=0.9,
                novelty=0.4,
                lines_planned=80,
                files_planned=("config.py",),
            ),
        ],
    )
