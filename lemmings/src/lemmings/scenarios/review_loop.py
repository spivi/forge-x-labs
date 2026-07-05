"""Level: review keeps failing → retry-loop bounded → escalation.

Disruptor at clock=0 forces every reviewer outcome to violate the
threshold (via the false-positive rate prior knob). Asserts the loop is
capped at `max_attempts` and the ticket is `ESCALATED`.
"""

from __future__ import annotations

from lemmings.schemas import RiskClass, Ticket
from lemmings.sim.des import Clock
from lemmings.sim.priors import load_default_priors
from lemmings.sim.scenario import Scenario
from lemmings.sim.trace import Trace
from lemmings.world.protocol import World


def _force_review_failures(_clock: Clock, _world: World, trace: Trace) -> None:
    trace.record(0.0, "DISRUPTOR_REVIEW_FAILURE_INJECTED")


def _failing_priors():  # type: ignore[no-untyped-def]
    p = load_default_priors()
    # threshold=0 + fp_rate=1.0 ⇒ every review FAILs deterministically
    p.review.violation_threshold = 0
    p.agents["code_reviewer"].false_positive_rate = 1.0
    # shorten cycles so 3 retries fit in `run_until_min`
    p.developer.duration_mu = 1.0
    p.developer.duration_lines_coef = 0.2
    p.developer.duration_sigma = 0.2
    p.review.duration_mu = 0.5
    p.review.duration_lines_coef = 0.2
    p.review.duration_sigma = 0.2
    return p


def build() -> Scenario:
    return Scenario(
        name="review_loop",
        sprint_budget_usd=200.0,  # plenty — we want the retry path, not budget
        budget_review_interval_min=30.0,
        run_until_min=60 * 24,  # 24h ceiling
        priors=_failing_priors(),
        initial_backlog=[
            Ticket(
                id="LEM-10",
                title="hard ticket",
                risk_class=RiskClass.AUTH,
                complexity=1.5,
                novelty=0.6,
                lines_planned=80,
                files_planned=("auth.py",),
            ),
        ],
        pre_run_events=[(0.0, _force_review_failures)],
    )
