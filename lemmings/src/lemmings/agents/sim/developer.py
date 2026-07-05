"""SimDeveloper — samples a developer outcome from priors and schedules it."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from random import Random

from lemmings.schemas import (
    PR,
    AgentKind,
    LedgerRow,
    Ticket,
    TicketStatus,
)
from lemmings.sim.des import Clock
from lemmings.sim.latents import (
    TicketLatents,
    sample_developer_outcome,
)
from lemmings.sim.priors import Priors
from lemmings.sim.trace import Trace
from lemmings.world.protocol import World

DoneCallback = Callable[[Clock, str], None]


class SimDeveloper:
    kind = AgentKind.DEVELOPER

    def __init__(self, rng: Random, priors: Priors) -> None:
        self.rng = rng
        self.priors = priors

    def run(
        self,
        clock: Clock,
        world: World,
        trace: Trace,
        ticket: Ticket,
        latents: TicketLatents,
        developer_quality_today: float,
        on_done: DoneCallback,
    ) -> None:
        outcome = sample_developer_outcome(
            self.rng, self.priors, latents, developer_quality_today
        )
        trace.record(
            clock.now,
            "DEVELOPER_STARTED",
            ticket_id=ticket.id,
            duration_min=outcome.duration_min,
            cost_estimate=outcome.cost_usd,
        )

        def _complete(c: Clock) -> None:
            world.append_ledger(
                LedgerRow(
                    timestamp=datetime.now(UTC).isoformat(),
                    agent="developer",
                    session_id=str(uuid.uuid4()),
                    provider="sim",
                    model="sim-developer",
                    input_tokens=int(outcome.duration_min * 1000),
                    output_tokens=int(outcome.duration_min * 200),
                    cache_creation_tokens=0,
                    cache_read_tokens=0,
                    compute_cost_usd=outcome.cost_usd,
                    billing_type="sim",
                    billed_usd=outcome.cost_usd,
                    ticket=ticket.id,
                )
            )
            existing = world.get_pr(ticket.id)
            if existing is None:
                world.open_pr(
                    PR(
                        ticket_id=ticket.id,
                        branch=f"feat/{ticket.id}",
                        files_touched=ticket.files_planned,
                        lines_added=outcome.lines_added,
                        bugs_introduced=outcome.bugs_introduced,
                        opened_at=c.now,
                    )
                )
            world.update_ticket_status(ticket.id, TicketStatus.IN_REVIEW)
            trace.record(
                c.now,
                "DEVELOPER_COMPLETED",
                ticket_id=ticket.id,
                bugs_introduced=outcome.bugs_introduced,
                lines_added=outcome.lines_added,
                cost=outcome.cost_usd,
            )
            on_done(c, ticket.id)

        clock.schedule(outcome.duration_min, _complete, label=f"developer_done:{ticket.id}")
