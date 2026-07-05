"""AI Code Review retry-loop decision logic.

Extracted from `.dev-context/rules/git.md` §6 (AI Code Review Gate).
Caps automated rework attempts at `max_attempts`; beyond that, escalate.
"""

from __future__ import annotations

from dataclasses import dataclass

from lemmings.schemas import ReviewVerdict
from lemmings.world.protocol import World


@dataclass(frozen=True)
class RetryDecision:
    action: str  # "merge" | "rework" | "escalate"
    attempts_used: int
    max_attempts: int
    last_verdict: ReviewVerdict | None


def evaluate_retry(world: World, ticket_id: str, max_attempts: int = 3) -> RetryDecision:
    """Decide what to do after a review completes.

    - PASS                         → merge
    - FAIL & attempts < max        → rework (developer revises)
    - FAIL & attempts ≥ max        → escalate (human signoff required)
    """
    reviews = world.list_reviews(ticket_id)
    if not reviews:
        raise ValueError(f"no reviews recorded for ticket {ticket_id}")

    last = reviews[-1]
    attempts = len(reviews)

    if last.verdict is ReviewVerdict.PASS:
        return RetryDecision(
            action="merge",
            attempts_used=attempts,
            max_attempts=max_attempts,
            last_verdict=last.verdict,
        )
    if attempts >= max_attempts:
        return RetryDecision(
            action="escalate",
            attempts_used=attempts,
            max_attempts=max_attempts,
            last_verdict=last.verdict,
        )
    return RetryDecision(
        action="rework",
        attempts_used=attempts,
        max_attempts=max_attempts,
        last_verdict=last.verdict,
    )
