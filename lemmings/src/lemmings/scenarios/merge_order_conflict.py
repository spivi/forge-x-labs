"""Level: two PRs touch the same file → must serialize.

Two backlog tickets share `auth.py`. Both make it to PR; orchestrator's
merge-order plan must serialize them. Asserts no two conflicting
tickets are reported as merged at the same clock.
"""

from __future__ import annotations

from lemmings.schemas import RiskClass, Ticket
from lemmings.sim.priors import load_default_priors
from lemmings.sim.scenario import Scenario


def _tight_priors():  # type: ignore[no-untyped-def]
    """Lock dev/review duration variance so both tickets reach PR within
    a tight window — guarantees the conflict is visible in MERGE_PLAN.
    """
    p = load_default_priors()
    p.developer.duration_sigma = 0.05
    p.review.duration_sigma = 0.05
    return p


def build() -> Scenario:
    return Scenario(
        name="merge_order_conflict",
        sprint_budget_usd=200.0,
        budget_review_interval_min=30.0,
        run_until_min=60 * 8,
        priors=_tight_priors(),
        initial_backlog=[
            Ticket(
                id="LEM-21",
                title="auth: refactor login",
                risk_class=RiskClass.AUTH,
                lines_planned=80,
                files_planned=("auth.py", "session.py"),
            ),
            Ticket(
                id="LEM-22",
                title="auth: rotate tokens",
                risk_class=RiskClass.AUTH,
                lines_planned=80,
                files_planned=("auth.py", "tokens.py"),
            ),
        ],
    )
