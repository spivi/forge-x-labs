"""Sprint planning logic extracted from Scrum Master skill.

Pure functions for capacity assessment, ticket selection, conflict
detection, and sprint log management. No external API calls.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

MAX_PARALLEL_AGENTS = 3


@dataclass(frozen=True)
class WorktreeEntry:
    """One row from the Active Worktrees table in STATUS.md."""

    branch: str
    worktree_dir: str
    ticket: str
    agent: str
    status: str
    files_touched: set[str] = field(default_factory=set)


@dataclass
class Ticket:
    """A backlog ticket for sprint planning."""

    number: str
    title: str
    priority: int
    files: set[str] = field(default_factory=set)
    depends_on: list[str] = field(default_factory=list)
    has_acceptance_criteria: bool = True


@dataclass(frozen=True)
class SkippedTicket:
    """A ticket that was not selected, with the reason."""

    ticket: Ticket
    reason: str


def parse_active_worktrees(status_content: str) -> list[WorktreeEntry]:
    """Parse the Active Worktrees markdown table from STATUS.md.

    Expects a table with columns:
    | Branch | Worktree Dir | Ticket | Agent | Status | Files Touched |

    Returns an empty list if no valid rows are found.
    """
    lines = status_content.splitlines()
    table_start = -1
    for i, line in enumerate(lines):
        if re.match(r"\s*\|\s*Branch\s*\|", line, re.IGNORECASE):
            table_start = i
            break
    if table_start == -1:
        return []

    entries: list[WorktreeEntry] = []
    for line in lines[table_start + 2 :]:
        line = line.strip()
        if not line.startswith("|"):
            break
        cells = [c.strip() for c in line.split("|")[1:-1]]
        if len(cells) < 6:
            continue
        branch, wt_dir, ticket, agent, status, files_str = cells[:6]
        if branch in ("(none)", "\u2014", "-", "") or ticket in (
            "\u2014",
            "-",
            "",
        ):
            continue
        files = {f.strip() for f in files_str.split(",") if f.strip() and f.strip() != "\u2014"}
        entries.append(
            WorktreeEntry(
                branch=branch,
                worktree_dir=wt_dir,
                ticket=ticket,
                agent=agent,
                status=status,
                files_touched=files,
            )
        )
    return entries


def calculate_capacity(
    active_count: int,
    max_parallel: int = MAX_PARALLEL_AGENTS,
) -> int:
    """Return available agent slots.

    Never returns negative (if active > max, returns 0).
    """
    return max(0, max_parallel - active_count)


def detect_file_conflicts(
    proposed_files: set[str],
    active: list[WorktreeEntry],
) -> dict[str, set[str]]:
    """Detect file overlaps between proposed work and active worktrees.

    Returns a dict mapping conflicting branch names to the set of
    overlapping files. Empty dict means no conflicts.
    """
    conflicts: dict[str, set[str]] = {}
    for entry in active:
        overlap = proposed_files & entry.files_touched
        if overlap:
            conflicts[entry.branch] = overlap
    return conflicts


def select_tickets(
    backlog: list[Ticket],
    active: list[WorktreeEntry],
    capacity: int,
) -> tuple[list[Ticket], list[SkippedTicket]]:
    """Select tickets for sprint assignment.

    Selection rules (from scrum_master.md Process section 2):
    1. Sort backlog by priority (P0 first)
    2. Skip tickets without acceptance criteria
    3. Skip tickets with file conflicts against active work
    4. Skip tickets with unmet dependencies
    5. Fill available slots up to capacity

    Returns (assigned, skipped) tuple.
    """
    sorted_backlog = sorted(backlog, key=lambda t: t.priority)
    active_tickets = {e.ticket for e in active}
    assigned: list[Ticket] = []
    skipped: list[SkippedTicket] = []
    assigned_files: set[str] = set()
    for entry in active:
        assigned_files |= entry.files_touched

    for ticket in sorted_backlog:
        if len(assigned) >= capacity:
            break

        if not ticket.has_acceptance_criteria:
            skipped.append(
                SkippedTicket(
                    ticket=ticket,
                    reason="missing acceptance criteria",
                )
            )
            continue

        conflicts = detect_file_conflicts(ticket.files, active)
        self_conflicts = ticket.files & assigned_files
        if conflicts or self_conflicts:
            branches = list(conflicts.keys())
            skipped.append(
                SkippedTicket(
                    ticket=ticket,
                    reason=(f"file conflict with {branches or 'assigned tickets'}"),
                )
            )
            continue

        unmet = [dep for dep in ticket.depends_on if dep not in active_tickets]
        if unmet:
            skipped.append(
                SkippedTicket(
                    ticket=ticket,
                    reason=f"blocked by unfinished: {unmet}",
                )
            )
            continue

        assigned.append(ticket)
        assigned_files |= ticket.files

    return assigned, skipped
