"""Escalation decision — when human signoff is required."""

from __future__ import annotations

from dataclasses import dataclass

from lemmings.core.retry_loop import evaluate_retry
from lemmings.world.protocol import World


@dataclass(frozen=True)
class EscalationDecision:
    should_escalate: bool
    reason: str


def evaluate_escalation(
    world: World, ticket_id: str, max_attempts: int = 3
) -> EscalationDecision:
    """Escalate if the retry loop has exhausted its budget."""
    decision = evaluate_retry(world, ticket_id, max_attempts=max_attempts)
    if decision.action == "escalate":
        return EscalationDecision(
            should_escalate=True,
            reason=f"retry_loop_exhausted_{decision.attempts_used}",
        )
    return EscalationDecision(should_escalate=False, reason="ok")
