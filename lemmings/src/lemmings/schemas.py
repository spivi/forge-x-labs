"""Core data types shared across world, agents, and decision core.

`LedgerRow` mirrors `.dev-context/cost-ledger.csv` (13 columns) so that
SimWorld → RealWorld handoff is a no-op.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class RiskClass(str, Enum):
    GENERIC = "generic"
    AUTH = "auth"
    PAYMENT = "payment"
    SCRAPING = "scraping"
    RECIPE_FETCH = "recipe-fetch"


class TicketStatus(str, Enum):
    BACKLOG = "backlog"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    REVIEW_FAILED = "review_failed"
    READY_TO_MERGE = "ready_to_merge"
    MERGED = "merged"
    ESCALATED = "escalated"
    BLOCKED = "blocked"


class ReviewVerdict(str, Enum):
    PASS = "pass"
    FAIL = "fail"


class AgentKind(str, Enum):
    SCRUM_MASTER = "scrum_master"
    DEVELOPER = "developer"
    CODE_REVIEWER = "code_reviewer"
    BUDGET_REVIEW = "budget_review"
    SECURITY_ARCHITECT = "security_architect"
    E2E_TESTER = "e2e_tester"
    PM = "pm"
    HANDOFF_MANAGER = "handoff_manager"


@dataclass
class Ticket:
    """A unit of work moving through the pipeline.

    Latents are sampled by `sim.latents.sample_ticket_latents` at scenario
    setup; downstream agents read them to produce observable outcomes.
    """

    id: str
    title: str
    risk_class: RiskClass = RiskClass.GENERIC
    status: TicketStatus = TicketStatus.BACKLOG
    complexity: float = 1.0
    novelty: float = 0.5
    lines_planned: int = 100
    files_planned: tuple[str, ...] = ()
    review_attempts: int = 0
    assigned_at: float | None = None
    merged_at: float | None = None


@dataclass
class PR:
    """A pull request produced by the developer for a ticket."""

    ticket_id: str
    branch: str
    files_touched: tuple[str, ...]
    lines_added: int
    bugs_introduced: int
    opened_at: float


@dataclass
class LedgerRow:
    """Mirrors `.dev-context/cost-ledger.csv` schema (13 columns)."""

    timestamp: str
    agent: str
    session_id: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cache_creation_tokens: int
    cache_read_tokens: int
    compute_cost_usd: float
    billing_type: str
    billed_usd: float
    ticket: str

    HEADER: tuple[str, ...] = field(
        default=(
            "timestamp",
            "agent",
            "session_id",
            "provider",
            "model",
            "input_tokens",
            "output_tokens",
            "cache_creation_tokens",
            "cache_read_tokens",
            "compute_cost_usd",
            "billing_type",
            "billed_usd",
            "ticket",
        ),
        repr=False,
    )


@dataclass
class ReviewResult:
    ticket_id: str
    verdict: ReviewVerdict
    violations: int
    duration_min: float


@dataclass
class TraceEvent:
    """A single recorded event. `payload` is JSON-serialisable."""

    clock: float
    kind: str
    payload: dict[str, object]
