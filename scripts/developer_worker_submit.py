"""Developer Worker submit: commit, PR, failure recovery, status updates.

Functions: format_commit_message, validate_commit_message,
generate_pr_description, format_pr_body, classify_failure,
should_escalate, format_escalation_message, format_status_update.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from developer_worker_io import (
    CommitMessage,
    FailureEscalation,
    PRDescription,
    ValidationResult,
)

if TYPE_CHECKING:
    from developer_worker import PlanSummary, TicketInput

# -- Commit Formatting (Phase 3) --------------------------------------------

_COMMIT_RE = re.compile(r"^(feat|fix|refactor|test|docs|chore|perf)(\(.+\))?: .+")
_PAST_TENSE_RE = re.compile(r"^(feat|fix|refactor|test|docs|chore|perf)(\(.+\))?: (\w+ed)\b")
_GERUND_RE = re.compile(r"^(feat|fix|refactor|test|docs|chore|perf)(\(.+\))?: (\w+ing)\b")


def format_commit_message(msg: CommitMessage) -> str:
    """Format CommitMessage as conventional commit string."""
    header = f"{msg.type}({msg.scope}): {msg.subject}"
    parts = [header]
    if msg.body:
        parts.append("")
        parts.append(msg.body)
    if msg.breaking:
        parts.append("")
        parts.append(f"BREAKING CHANGE: {msg.subject}")
    return "\n".join(parts)


def validate_commit_message(message: str) -> list[str]:
    """Validate a commit message against conventional commit rules."""
    violations: list[str] = []
    first_line = message.split("\n")[0]
    if not _COMMIT_RE.match(first_line):
        violations.append("Missing conventional commit type prefix")
        return violations
    subject = first_line.split(": ", 1)[1] if ": " in first_line else ""
    if len(first_line) > 72:
        violations.append("Subject line exceeds 72 characters")
    if subject.endswith("."):
        violations.append("Subject has trailing period")
    if _PAST_TENSE_RE.match(first_line):
        violations.append("Subject not in imperative mood (past tense)")
    if _GERUND_RE.match(first_line):
        violations.append("Subject not in imperative mood (gerund)")
    return violations


# -- PR Generation (Phase 6) ------------------------------------------------


def generate_pr_description(
    plan: PlanSummary,
    ticket: TicketInput,
    validations: list[ValidationResult],
) -> PRDescription:
    """Generate PR description from plan + ticket + validation results."""
    has_create = bool(plan.files_to_create)
    pr_type = "feat" if has_create else "fix"
    title = f"{pr_type}({ticket.ticket_id}): {ticket.title}"
    summary = []
    if plan.files_to_create:
        summary.append(f"Create: {', '.join(plan.files_to_create)}")
    if plan.files_to_modify:
        summary.append(f"Modify: {', '.join(plan.files_to_modify)}")
    if plan.test_files:
        summary.append(f"Tests: {', '.join(plan.test_files)}")
    test_plan = ["Run pytest on test files"]
    if validations:
        for v in validations:
            test_plan.append(f"{v.tool}: {'PASS' if v.passed else 'FAIL'}")
    all_files = plan.files_to_create + plan.files_to_modify + plan.test_files
    return PRDescription(
        title=title,
        summary=summary,
        ticket_id=ticket.ticket_id,
        test_plan=test_plan,
        files_changed=all_files,
    )


def format_pr_body(pr: PRDescription) -> str:
    """Format PR description as markdown body."""
    lines = ["## Summary"]
    for item in pr.summary:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Ticket")
    lines.append(pr.ticket_id)
    lines.append("")
    lines.append("## Test Plan")
    for step in pr.test_plan:
        lines.append(f"- {step}")
    return "\n".join(lines)


# -- Failure Recovery (Phase 5) ---------------------------------------------


def classify_failure(result: ValidationResult, attempt: int) -> FailureEscalation:
    """Determine escalation action based on failure type and attempt count."""
    if result.tool == "conflict":
        return FailureEscalation(
            failure_type="conflict",
            attempts=attempt,
            last_error=result.output,
            recommendation="escalate_scrum_master",
        )
    if result.tool == "mypy" and any(
        kw in (result.output + " ".join(result.errors))
        for kw in ("no-untyped", "external", "no-untyped-def")
    ):
        return FailureEscalation(
            failure_type="type_check",
            attempts=attempt,
            last_error=result.output,
            recommendation="add_type_ignore",
        )
    if result.tool == "pre-commit":
        return FailureEscalation(
            failure_type="pre-commit",
            attempts=attempt,
            last_error=result.output,
            recommendation="fix_violation",
        )
    if attempt >= 3:
        return FailureEscalation(
            failure_type=result.tool,
            attempts=attempt,
            last_error=result.output,
            recommendation="draft_pr",
        )
    return FailureEscalation(
        failure_type=result.tool,
        attempts=attempt,
        last_error=result.output,
        recommendation="retry",
    )


def should_escalate(attempt: int, max_attempts: int = 3) -> bool:
    """Return True if max fix attempts exceeded."""
    return attempt >= max_attempts


def format_escalation_message(escalation: FailureEscalation) -> str:
    """Format escalation as a structured message for Scrum Master."""
    return (
        f"Failure Type: {escalation.failure_type}\n"
        f"Attempts: {escalation.attempts}\n"
        f"Last Error: {escalation.last_error}\n"
        f"Recommendation: {escalation.recommendation}"
    )


# -- STATUS.md Updates (Phase 6) -------------------------------------------


def format_status_update(
    branch: str,
    ticket_id: str,
    status: str,
    files_touched: list[str],
) -> str:
    """Format a worktree table row for STATUS.md."""
    wt_dir = f"{{{{PROJECT_NAME}}}}--{ticket_id}"
    files_str = ", ".join(files_touched) or "(tbd)"
    return f"| {branch} | {wt_dir} | {ticket_id} | Claude | {status} | {files_str} |"
