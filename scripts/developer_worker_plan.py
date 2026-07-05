"""Developer Worker planning: conflict detection, scope, missing context.

Functions: detect_file_conflicts, build_plan_summary, check_scope_creep,
detect_ambiguous_criteria, detect_missing_context.
"""

from __future__ import annotations

from developer_worker import (
    FileConflict,
    PlanSummary,
    TicketInput,
    WorktreeContext,
)

TESTABLE_VERBS = frozenset(
    {
        "verify",
        "return",
        "display",
        "show",
        "create",
        "delete",
        "update",
        "send",
        "receive",
        "parse",
        "validate",
        "generate",
        "format",
        "check",
        "detect",
        "extract",
        "calculate",
        "group",
        "filter",
        "sort",
    }
)

VAGUE_PHRASES = frozenset({"should work", "looks good", "is nice", "is fine", "tbd", "todo"})

ARCH_KEYWORDS = frozenset({"auth", "security", "cache", "caching", "database", "migration"})


def detect_file_conflicts(
    proposed_files: set[str],
    active_worktrees: list[tuple[str, str, set[str]]],
) -> list[FileConflict]:
    """Check proposed files against active worktree files."""
    conflicts: list[FileConflict] = []
    for branch, ticket, files in active_worktrees:
        for f in proposed_files & files:
            conflicts.append(
                FileConflict(
                    file_path=f,
                    conflicting_branch=branch,
                    conflicting_ticket=ticket,
                )
            )
    return conflicts


def build_plan_summary(
    files_to_create: list[str],
    files_to_modify: list[str],
    test_files: list[str],
    context: WorktreeContext,
) -> PlanSummary:
    """Build plan summary with conflict detection and scope check."""
    all_files = set(files_to_create) | set(files_to_modify) | set(test_files)
    total = len(all_files)
    wt = [(b, t, f) for b, t, f in context.active_worktrees] if context.active_worktrees else []
    avoid_tuples: list[tuple[str, str, set[str]]] = []
    if context.files_to_avoid:
        avoid_tuples = [("active-branch", "unknown", context.files_to_avoid)]
    conflicts = detect_file_conflicts(all_files, avoid_tuples or wt)
    scope_warning = check_scope_creep(context.ticket, all_files)
    return PlanSummary(
        files_to_create=files_to_create,
        files_to_modify=files_to_modify,
        test_files=test_files,
        conflicts=conflicts,
        needs_summary=total > 3,
        scope_warning=scope_warning,
    )


def check_scope_creep(ticket: TicketInput, proposed_files: set[str]) -> str:
    """Return scope warning if proposed files seem unrelated."""
    if not ticket.context_files:
        if proposed_files:
            unrelated = sorted(proposed_files)
            return (
                "No context files in ticket; all proposed files are unscoped: "
                f"{', '.join(unrelated)}"
            )
        return ""
    ctx_set = set(ticket.context_files)
    ticket_pattern = ticket.ticket_id.replace("-", "_") if ticket.ticket_id else ""
    unrelated = []
    for f in proposed_files:
        if f in ctx_set:
            continue
        if ticket_pattern and ticket_pattern.lower() in f.lower():
            continue
        unrelated.append(f)
    if unrelated:
        return f"Possible scope creep: {', '.join(sorted(unrelated))}"
    return ""


def detect_ambiguous_criteria(criteria: list[str]) -> list[str]:
    """Flag acceptance criteria that are too vague to implement."""
    flagged: list[str] = []
    for c in criteria:
        lower = c.lower()
        if len(c) < 10:
            flagged.append(c)
            continue
        if any(vp in lower for vp in VAGUE_PHRASES):
            flagged.append(c)
            continue
        words = {w.strip(".,;:!?") for w in lower.split()}
        has_verb = any(w.startswith(v) for w in words for v in TESTABLE_VERBS)
        if not has_verb:
            flagged.append(c)
    return flagged


def detect_missing_context(
    ticket: TicketInput,
    decisions_content: str,
) -> list[str]:
    """Detect gaps the developer should flag, not hallucinate."""
    gaps: list[str] = []
    if not ticket.acceptance_criteria:
        gaps.append("No acceptance criteria")
    if not ticket.context_files:
        gaps.append("No context files")
    title_lower = (ticket.title + " ".join(ticket.acceptance_criteria)).lower()
    if any(kw in title_lower for kw in ARCH_KEYWORDS) and not decisions_content.strip():
        gaps.append("References architectural pattern but no decisions available")
    return gaps
