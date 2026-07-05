"""SimScrumMaster — orchestrator loop using the decision core.

Drives the pipeline: budget gate → ticket selection → developer →
reviewer → retry/escalate → merge ordering. All decisions flow through
`lemmings.core.*` so the same code path runs against `RealWorld` (v2).
"""

from __future__ import annotations

from random import Random

from lemmings.agents.sim.code_reviewer import SimCodeReviewer
from lemmings.agents.sim.developer import SimDeveloper
from lemmings.core.budget_gate import evaluate_budget
from lemmings.core.merge_order import plan_merges
from lemmings.core.retry_loop import evaluate_retry
from lemmings.core.select_ticket import select_next_ticket
from lemmings.schemas import AgentKind, TicketStatus
from lemmings.sim.des import Clock
from lemmings.sim.latents import (
    TicketLatents,
    sample_developer_quality_today,
)
from lemmings.sim.priors import Priors
from lemmings.sim.trace import Trace
from lemmings.world.protocol import World


class SimScrumMaster:
    kind = AgentKind.SCRUM_MASTER

    def __init__(
        self,
        rng: Random,
        priors: Priors,
        world: World,
        trace: Trace,
        developer: SimDeveloper | None = None,
        reviewer: SimCodeReviewer | None = None,
    ) -> None:
        self.rng = rng
        self.priors = priors
        self.world = world
        self.trace = trace
        self.developer = developer or SimDeveloper(rng, priors)
        self.reviewer = reviewer or SimCodeReviewer(rng, priors)
        self._dev_quality: dict[str, float] = {}
        self._ticket_latents: dict[str, TicketLatents] = {}
        self._halted: bool = False

    # ---- public entry points ----

    def kickoff(self, clock: Clock) -> None:
        """Begin the sprint at clock=now."""
        self.trace.record(clock.now, "SPRINT_STARTED")
        self._tick(clock)

    # ---- orchestration ----

    def _tick(self, clock: Clock) -> None:
        """Dispatch every backlog ticket the budget gate still allows.

        Called at kickoff and after every merge/escalate so newly-arrived
        tickets get picked up. Sequential within a tick — but multiple
        tickets dispatched in the same tick run in parallel via the DES.
        """
        if self._halted:
            return
        while True:
            budget = evaluate_budget(
                self.world, hard_cap_factor=self.priors.budget.hard_cap_factor
            )
            self.trace.record(
                clock.now,
                "BUDGET_EVAL",
                allow=budget.allow,
                reason=budget.reason,
                spent=budget.spent_usd,
                hard_cap=budget.hard_cap_usd,
            )
            if not budget.allow:
                self.trace.record(
                    clock.now,
                    "BUDGET_EXCEEDED",
                    reason=budget.reason,
                    spent=budget.spent_usd,
                )
                self._halted = True
                return

            ticket = select_next_ticket(self.world)
            if ticket is None:
                self.trace.record(clock.now, "BACKLOG_EMPTY")
                return

            self.world.update_ticket_status(ticket.id, TicketStatus.IN_PROGRESS)
            self.trace.record(clock.now, "TICKET_ASSIGNED", ticket_id=ticket.id)

            if ticket.id not in self._ticket_latents:
                # Latents come from the ticket spec — the scenario IS authoritative
                # for `complexity`, `novelty`, `lines_planned`. Random sampling is
                # reserved for correlation self-tests (see test_correlations.py).
                self._ticket_latents[ticket.id] = TicketLatents(
                    complexity=ticket.complexity,
                    novelty=ticket.novelty,
                    lines_planned=ticket.lines_planned,
                )
            if ticket.id not in self._dev_quality:
                self._dev_quality[ticket.id] = sample_developer_quality_today(
                    self.rng, self.priors
                )

            self.developer.run(
                clock,
                self.world,
                self.trace,
                ticket=ticket,
                latents=self._ticket_latents[ticket.id],
                developer_quality_today=self._dev_quality[ticket.id],
                on_done=self._on_developer_done,
            )

    def _on_developer_done(self, clock: Clock, ticket_id: str) -> None:
        # gate again now that the developer's spend is on the ledger
        budget = evaluate_budget(self.world, hard_cap_factor=self.priors.budget.hard_cap_factor)
        if not budget.allow:
            self.trace.record(
                clock.now,
                "BUDGET_EXCEEDED",
                reason=f"post_developer:{budget.reason}",
                spent=budget.spent_usd,
            )
            self._halted = True
            return

        pr = self.world.get_pr(ticket_id)
        if pr is None:
            raise RuntimeError(f"developer finished {ticket_id} but no PR was opened")

        self.reviewer.run(
            clock,
            self.world,
            self.trace,
            pr=pr,
            developer_quality_today=self._dev_quality[ticket_id],
            on_done=self._on_review_done,
        )

    def _on_review_done(self, clock: Clock, ticket_id: str) -> None:
        decision = evaluate_retry(
            self.world, ticket_id, max_attempts=self.priors.retry.max_attempts
        )
        self.trace.record(
            clock.now,
            "RETRY_DECISION",
            ticket_id=ticket_id,
            action=decision.action,
            attempts=decision.attempts_used,
            max_attempts=decision.max_attempts,
        )

        if decision.action == "merge":
            self._attempt_merge(clock, ticket_id)
        elif decision.action == "rework":
            self.world.update_ticket_status(ticket_id, TicketStatus.REVIEW_FAILED)
            self.trace.record(
                clock.now,
                "REWORK_DISPATCHED",
                ticket_id=ticket_id,
                attempts=decision.attempts_used,
            )
            ticket = self.world.get_ticket(ticket_id)
            self.developer.run(
                clock,
                self.world,
                self.trace,
                ticket=ticket,
                latents=self._ticket_latents[ticket_id],
                developer_quality_today=self._dev_quality[ticket_id],
                on_done=self._on_developer_done,
            )
        else:  # escalate
            self.world.update_ticket_status(ticket_id, TicketStatus.ESCALATED)
            self.trace.record(
                clock.now,
                "ESCALATED",
                ticket_id=ticket_id,
                attempts=decision.attempts_used,
            )
            self._tick(clock)

    def _attempt_merge(self, clock: Clock, ticket_id: str) -> None:
        plan = plan_merges(self.world.list_open_prs())
        self.trace.record(
            clock.now,
            "MERGE_PLAN",
            order=list(plan.order),
            conflicts=[list(p) for p in plan.conflict_pairs],
        )
        if ticket_id not in plan.order:
            self.world.update_ticket_status(ticket_id, TicketStatus.READY_TO_MERGE)
            self.trace.record(clock.now, "MERGE_BLOCKED", ticket_id=ticket_id)
            self._tick(clock)
            return
        self.world.close_pr(ticket_id, merged=True)
        self.trace.record(clock.now, "MERGED", ticket_id=ticket_id)
        self._tick(clock)
