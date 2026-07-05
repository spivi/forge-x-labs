"""Developer Worker agent -- data models + orientation functions.

Data models: TicketInput, WorktreeContext, FileConflict, PlanSummary.
Functions: parse_ticket_input, parse_active_worktrees_for_avoidance,
parse_decisions_list, build_worktree_context.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class TicketInput:
    """Parsed ticket for developer worker."""

    ticket_id: str
    title: str
    acceptance_criteria: list[str] = field(default_factory=list)
    priority: str = "P2"
    context_files: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class WorktreeContext:
    """Orientation phase output: parsed context for development."""

    ticket: TicketInput
    active_worktrees: list[tuple[str, str, set[str]]] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    files_to_avoid: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class FileConflict:
    """A file conflict between proposed work and active branches."""

    file_path: str
    conflicting_branch: str
    conflicting_ticket: str


@dataclass(frozen=True)
class PlanSummary:
    """Plan phase output: what the developer intends to do."""

    files_to_create: list[str] = field(default_factory=list)
    files_to_modify: list[str] = field(default_factory=list)
    test_files: list[str] = field(default_factory=list)
    conflicts: list[FileConflict] = field(default_factory=list)
    needs_summary: bool = False
    scope_warning: str = ""


# -- Orientation (Phase 1) --------------------------------------------------

_TICKET_RE = re.compile(r"^\s*({{TICKET_PREFIX}}-\d+):?\s*(.*)", re.MULTILINE)


def parse_ticket_input(raw: str) -> TicketInput:
    """Parse raw ticket text into TicketInput."""
    raw = raw.strip()
    if not raw:
        return TicketInput(ticket_id="", title="")

    ticket_id, title = "", ""
    m = _TICKET_RE.search(raw)
    if m:
        ticket_id = m.group(1).strip()
        title = m.group(2).strip()

    ac: list[str] = []
    in_ac = False
    priority = "P2"
    context_files: list[str] = []

    for line in raw.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("AC:"):
            in_ac = True
            continue
        if in_ac and stripped.startswith("- "):
            ac.append(stripped[2:].strip())
            continue
        if in_ac and not stripped.startswith("- "):
            in_ac = False
        if stripped.lower().startswith("priority:"):
            priority = stripped.split(":", 1)[1].strip()
        if stripped.lower().startswith("context:"):
            ctx_str = stripped.split(":", 1)[1]
            context_files = [f.strip() for f in ctx_str.split(",") if f.strip()]

    return TicketInput(
        ticket_id=ticket_id,
        title=title,
        acceptance_criteria=ac,
        priority=priority,
        context_files=context_files,
    )


def parse_active_worktrees_for_avoidance(status_content: str) -> set[str]:
    """Extract files-to-avoid set from STATUS.md Active Worktrees table."""
    lines = status_content.splitlines()
    header_idx = -1
    for i, line in enumerate(lines):
        if re.match(r"\s*\|\s*Branch\s*\|", line, re.IGNORECASE):
            header_idx = i
            break
    if header_idx == -1:
        return set()

    avoid: set[str] = set()
    for line in lines[header_idx + 2 :]:
        line = line.strip()
        if not line.startswith("|"):
            break
        cells = [c.strip() for c in line.split("|")[1:-1]]
        if len(cells) < 6:
            continue
        branch = cells[0]
        if branch in ("(none)", "\u2014", "-", ""):
            continue
        files_str = cells[5]
        for f in files_str.split(","):
            f = f.strip()
            if f and f != "\u2014":
                avoid.add(f)
    return avoid


_DEC_ID_RE = re.compile(r"##\s+({{PROJECT_ID}}-D\d+):")
_DEC_STATUS_RE = re.compile(r"\*\*Status\*\*:\s*(\S+)")


def parse_decisions_list(decisions_content: str) -> list[str]:
    """Extract accepted decision IDs from DECISIONS.md."""
    if not decisions_content.strip():
        return []
    ids: list[str] = []
    blocks = re.split(r"^---\s*$", decisions_content, flags=re.MULTILINE)
    for block in blocks:
        id_m = _DEC_ID_RE.search(block)
        status_m = _DEC_STATUS_RE.search(block)
        if not id_m or not status_m:
            continue
        status = status_m.group(1).lower()
        if "superseded" in status or "deprecated" in status:
            continue
        ids.append(id_m.group(1))
    return ids


def build_worktree_context(
    ticket: TicketInput,
    status_content: str,
    decisions_content: str,
) -> WorktreeContext:
    """Combine parsed inputs into WorktreeContext."""
    avoid = parse_active_worktrees_for_avoidance(status_content)
    decisions = parse_decisions_list(decisions_content)
    return WorktreeContext(
        ticket=ticket,
        decisions=decisions,
        files_to_avoid=avoid,
    )
