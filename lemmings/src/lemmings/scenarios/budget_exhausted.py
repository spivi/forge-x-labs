"""Level: budget exhaustion.

A small sprint budget plus a backlog of tickets that *will* push spend
over the hard cap. Asserts the orchestrator stops dispatching once the
budget gate trips.
"""

from __future__ import annotations

from lemmings.schemas import RiskClass, Ticket
from lemmings.sim.scenario import Scenario


def build() -> Scenario:
    return Scenario(
        name="budget_exhausted",
        sprint_budget_usd=2.0,  # tiny — first ticket alone may blow it
        budget_review_interval_min=15.0,
        run_until_min=60 * 8,
        initial_backlog=[
            Ticket(
                id="LEM-1",
                title="task one",
                risk_class=RiskClass.GENERIC,
                files_planned=("a.py",),
            ),
            Ticket(
                id="LEM-2",
                title="task two",
                risk_class=RiskClass.GENERIC,
                files_planned=("b.py",),
            ),
            Ticket(
                id="LEM-3",
                title="task three",
                risk_class=RiskClass.GENERIC,
                files_planned=("c.py",),
            ),
            Ticket(
                id="LEM-4",
                title="task four",
                risk_class=RiskClass.GENERIC,
                files_planned=("d.py",),
            ),
        ],
    )
