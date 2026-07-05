"""SimCodeReviewer — samples a review outcome and records it."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from random import Random

from lemmings.schemas import (
    PR,
    AgentKind,
    LedgerRow,
    ReviewResult,
)
from lemmings.sim.des import Clock
from lemmings.sim.latents import sample_review_outcome
from lemmings.sim.priors import Priors
from lemmings.sim.trace import Trace
from lemmings.world.protocol import World

DoneCallback = Callable[[Clock, str], None]


class SimCodeReviewer:
    kind = AgentKind.CODE_REVIEWER

    def __init__(self, rng: Random, priors: Priors) -> None:
        self.rng = rng
        self.priors = priors

    def run(
        self,
        clock: Clock,
        world: World,
        trace: Trace,
        pr: PR,
        developer_quality_today: float,
        on_done: DoneCallback,
    ) -> None:
        outcome = sample_review_outcome(
            self.rng,
            self.priors,
            lines_added=pr.lines_added,
            bugs=pr.bugs_introduced,
            developer_quality_today=developer_quality_today,
        )
        trace.record(
            clock.now,
            "REVIEW_STARTED",
            ticket_id=pr.ticket_id,
            duration_min=outcome.duration_min,
        )

        def _complete(c: Clock) -> None:
            world.append_ledger(
                LedgerRow(
                    timestamp=datetime.now(UTC).isoformat(),
                    agent="code_reviewer",
                    session_id=str(uuid.uuid4()),
                    provider="sim",
                    model="sim-reviewer",
                    input_tokens=int(outcome.duration_min * 800),
                    output_tokens=int(outcome.duration_min * 100),
                    cache_creation_tokens=0,
                    cache_read_tokens=0,
                    compute_cost_usd=outcome.cost_usd,
                    billing_type="sim",
                    billed_usd=outcome.cost_usd,
                    ticket=pr.ticket_id,
                )
            )
            world.record_review(
                ReviewResult(
                    ticket_id=pr.ticket_id,
                    verdict=outcome.verdict,
                    violations=outcome.violations,
                    duration_min=outcome.duration_min,
                )
            )
            trace.record(
                c.now,
                "REVIEW_COMPLETED",
                ticket_id=pr.ticket_id,
                verdict=outcome.verdict.value,
                violations=outcome.violations,
                cost=outcome.cost_usd,
            )
            on_done(c, pr.ticket_id)

        clock.schedule(outcome.duration_min, _complete, label=f"review_done:{pr.ticket_id}")
