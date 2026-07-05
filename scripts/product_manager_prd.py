"""Product Manager agent — PRD generation, approval, and ticket creation.

Data models: AcceptanceCriterion, PRDDocument, ApprovalDecision, TicketSpec.
Functions: generate_prd, validate_prd, format_prd_markdown,
apply_approval, revise_prd, create_ticket_specs, format_ticket_body.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from product_manager import FeasibilityReport

STATUS_MAP = {
    "approve": "Approved",
    "reject": "Rejected",
    "defer": "Deferred",
    "revise": "Draft",
}

PRIORITY_FROM_COMPLEXITY = {"L": "P1", "M": "P2", "S": "P3"}


@dataclass(frozen=True)
class AcceptanceCriterion:
    """One testable acceptance criterion."""

    description: str
    is_testable: bool


@dataclass(frozen=True)
class PRDDocument:
    """Structured PRD ready for human review."""

    title: str
    status: str  # "Draft" | "Approved" | "Rejected" | "Deferred"
    priority: str  # "P0" | "P1" | "P2" | "P3"
    complexity: str  # "S" | "M" | "L"
    problem_statement: str
    proposed_solution: str
    acceptance_criteria: list[AcceptanceCriterion]
    scope_files: list[str]
    risks: list[str]
    out_of_scope: list[str]
    alternatives: list[str]


@dataclass(frozen=True)
class ApprovalDecision:
    """Human review outcome."""

    action: str  # "approve" | "revise" | "reject" | "defer"
    feedback: str
    prd_title: str


@dataclass(frozen=True)
class TicketSpec:
    """GitHub Issue specification (data only, no API call)."""

    title: str
    body: str
    labels: list[str]
    prd_title: str


def _build_criteria(report: FeasibilityReport) -> list[AcceptanceCriterion]:
    criteria = [
        AcceptanceCriterion(
            description=f"{m.file_path} supports {m.change_type}: {m.reason}",
            is_testable=True,
        )
        for m in report.affected_modules
    ]
    criteria.append(AcceptanceCriterion("All tests pass", is_testable=True))
    criteria.append(AcceptanceCriterion("No regressions", is_testable=True))
    return criteria


def generate_prd(feasibility: FeasibilityReport) -> PRDDocument:
    """Generate structured PRD from feasibility report."""
    title = feasibility.idea.problem[:80].capitalize()
    return PRDDocument(
        title=title,
        status="Draft",
        priority=PRIORITY_FROM_COMPLEXITY.get(feasibility.complexity, "P2"),
        complexity=feasibility.complexity,
        problem_statement=feasibility.idea.problem,
        proposed_solution=feasibility.idea.raw_text,
        acceptance_criteria=_build_criteria(feasibility),
        scope_files=[m.file_path for m in feasibility.affected_modules],
        risks=list(feasibility.risks),
        out_of_scope=[],
        alternatives=[],
    )


def validate_prd(prd: PRDDocument) -> list[str]:
    """Validate PRD completeness. Returns list of issues (empty = valid)."""
    issues: list[str] = []
    if not prd.title.strip():
        issues.append("Title is required")
    if len(prd.acceptance_criteria) < 2:
        issues.append("At least 2 acceptance criteria required")
    if any(not ac.is_testable for ac in prd.acceptance_criteria):
        issues.append("All acceptance criteria must be testable")
    if not prd.scope_files:
        issues.append("At least one scope file required")
    if not prd.problem_statement.strip():
        issues.append("Problem statement is required")
    return issues


def format_prd_markdown(prd: PRDDocument) -> str:
    """Render PRD as markdown string."""
    lines = [
        f"# PRD: {prd.title}",
        "",
        f"**Status:** {prd.status}  ",
        f"**Priority:** {prd.priority}  ",
        f"**Complexity:** {prd.complexity}",
        "",
        "## Problem Statement",
        "",
        prd.problem_statement,
        "",
        "## Proposed Solution",
        "",
        prd.proposed_solution,
        "",
        "## Acceptance Criteria",
        "",
    ]
    for ac in prd.acceptance_criteria:
        lines.append(f"- [ ] {ac.description}")
    lines += ["", "## Scope", ""]
    for path in prd.scope_files:
        lines.append(f"- `{path}`")
    if prd.risks:
        lines += ["", "## Risks", ""]
        for risk in prd.risks:
            lines.append(f"- {risk}")
    return "\n".join(lines) + "\n"


def apply_approval(prd: PRDDocument, decision: ApprovalDecision) -> PRDDocument:
    """Apply human decision to PRD. Returns new PRD with updated status."""
    new_status = STATUS_MAP.get(decision.action, prd.status)
    return replace(prd, status=new_status)


def revise_prd(prd: PRDDocument, feedback: str) -> PRDDocument:
    """Return new PRD incorporating revision feedback."""
    new_problem = f"{prd.problem_statement}\n\nRevised based on: {feedback}"
    new_risks = list(prd.risks) + [feedback]
    return replace(prd, problem_statement=new_problem, risks=new_risks, status="Draft")


BATCH_SIZE = 3  # scope files per ticket


def create_ticket_specs(prd: PRDDocument) -> list[TicketSpec]:
    """Generate GitHub Issue specs from approved PRD."""
    if prd.status != "Approved":
        return []
    labels = [
        f"priority:{prd.priority}",
        f"complexity:{prd.complexity}",
        "status:ready",
    ]
    tickets: list[TicketSpec] = []
    for i in range(0, max(1, len(prd.scope_files)), BATCH_SIZE):
        ticket_title = f"{{{{TICKET_PREFIX}}}}-XXX: {prd.title}"
        if len(prd.scope_files) > BATCH_SIZE:
            ticket_title += f" (part {i // BATCH_SIZE + 1})"
        tickets.append(
            TicketSpec(
                title=ticket_title,
                body=format_ticket_body(prd),
                labels=labels,
                prd_title=prd.title,
            )
        )
    return tickets


def format_ticket_body(prd: PRDDocument) -> str:
    """Format PRD content as GitHub Issue body markdown."""
    lines = [
        f"## {prd.title}",
        "",
        prd.problem_statement,
        "",
        "### Acceptance Criteria",
        "",
    ]
    for ac in prd.acceptance_criteria:
        lines.append(f"- [ ] {ac.description}")
    lines += ["", "### Scope Files", ""]
    for path in prd.scope_files:
        lines.append(f"- `{path}`")
    if prd.risks:
        lines += ["", "### Risks", ""]
        for risk in prd.risks:
            lines.append(f"- {risk}")
    return "\n".join(lines) + "\n"
