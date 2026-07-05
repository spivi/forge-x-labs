"""Sprint planning I/O: budget gate, sprint log, worktree table."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from sprint_planner import WorktreeEntry

SPRINT_LOG_HEADER = [
    "sprint_id",
    "start_date",
    "end_date",
    "planned_tickets",
    "completed_tickets",
    "conflicts",
    "avg_cycle_hours",
    "blockers_raised",
    "blockers_resolved",
]


@dataclass
class BudgetStatus:
    """Result of a budget gate check."""

    spend: float
    budget: float
    percent: float
    status: str  # "OK", "WARNING", "CRITICAL", "EXCEEDED"


@dataclass
class SprintEntry:
    """One row for sprint-log.csv."""

    sprint_id: str
    start_date: str
    end_date: str
    planned_tickets: int
    completed_tickets: int = 0
    conflicts: int = 0
    avg_cycle_hours: float = 0.0
    blockers_raised: int = 0
    blockers_resolved: int = 0


def check_budget_gate(
    budgets_path: Path,
    ledger_path: Path,
    status_content: str,
) -> BudgetStatus:
    """Check budget: BUDGET_EXCEEDED in STATUS.md or ledger vs budget."""
    if "BUDGET_EXCEEDED" in status_content:
        return BudgetStatus(spend=0.0, budget=0.0, percent=100.0, status="EXCEEDED")

    budget_total, alerts = _load_budgets_config(budgets_path)
    warn_pct = alerts.get("warn_at_percent", 70)
    critical_pct = alerts.get("critical_at_percent", 90)

    spend = _sum_today_spend(ledger_path)

    pct = (spend / budget_total * 100) if budget_total > 0 else 0.0
    if pct >= 100:
        status = "EXCEEDED"
    elif pct >= critical_pct:
        status = "CRITICAL"
    elif pct >= warn_pct:
        status = "WARNING"
    else:
        status = "OK"

    return BudgetStatus(spend=spend, budget=budget_total, percent=pct, status=status)


def _load_budgets_config(path: Path) -> tuple[float, dict[str, float]]:
    """Load daily budget and alert thresholds. Returns (budget, alerts)."""
    defaults = 20.0, {"warn_at_percent": 70, "critical_at_percent": 90}
    if not path.exists():
        return defaults
    import yaml

    with open(path) as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        return defaults
    budget = float(data.get("budgets", {}).get("daily", {}).get("total", 20.0))
    raw = data.get("alerts", {})
    alerts = {
        "warn_at_percent": float(raw.get("warn_at_percent", 70)),
        "critical_at_percent": float(raw.get("critical_at_percent", 90)),
    }
    return budget, alerts


def _sum_today_spend(ledger_path: Path) -> float:
    """Sum billed_usd from cost-ledger.csv for today (UTC)."""
    if not ledger_path.exists():
        return 0.0
    from datetime import UTC, datetime

    today = datetime.now(UTC).strftime("%Y-%m-%d")
    total = 0.0
    with open(ledger_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts_str = row.get("timestamp", "").strip().strip('"')
            if not ts_str.startswith(today):
                continue
            try:
                cost = float(row.get("billed_usd", "0").strip().strip('"'))
            except ValueError:
                continue
            total += cost
    return total


def update_sprint_log(log_path: Path, entry: SprintEntry) -> None:
    """Append a sprint entry to sprint-log.csv (creates if missing)."""
    write_header = not log_path.exists() or log_path.stat().st_size == 0
    if log_path.exists() and log_path.stat().st_size > 0:
        with open(log_path) as f:
            content = f.read().strip()
        if "\n" not in content:
            write_header = False

    with open(log_path, "a", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        if write_header:
            writer.writerow(SPRINT_LOG_HEADER)
        writer.writerow(
            [
                entry.sprint_id,
                entry.start_date,
                entry.end_date,
                entry.planned_tickets,
                entry.completed_tickets,
                entry.conflicts,
                f"{entry.avg_cycle_hours:.1f}",
                entry.blockers_raised,
                entry.blockers_resolved,
            ]
        )


def update_worktrees_table(
    status_content: str,
    new_entries: list[WorktreeEntry],
) -> str:
    """Return STATUS.md with new worktree entries replacing placeholder."""
    if not new_entries:
        return status_content

    lines = status_content.splitlines(keepends=True)
    header_idx = -1
    for i, line in enumerate(lines):
        if re.match(r"\s*\|\s*Branch\s*\|", line, re.IGNORECASE):
            header_idx = i
            break

    if header_idx == -1:
        return status_content

    sep_idx = header_idx + 1
    table_end = sep_idx + 1
    while table_end < len(lines) and lines[table_end].strip().startswith("|"):
        table_end += 1

    existing = lines[sep_idx + 1 : table_end]
    is_placeholder = all(
        "(none)" in row or all(c.strip() in ("\u2014", "-", "") for c in row.split("|")[1:-1])
        for row in existing
        if row.strip().startswith("|")
    )

    new_rows: list[str] = []
    for entry in new_entries:
        files_str = ", ".join(sorted(entry.files_touched)) or "(tbd)"
        new_rows.append(
            f"| {entry.branch} | {entry.worktree_dir} "
            f"| {entry.ticket} | {entry.agent} "
            f"| {entry.status} | {files_str} |\n"
        )

    if is_placeholder:
        result = lines[: sep_idx + 1] + new_rows + lines[table_end:]
    else:
        result = lines[:table_end] + new_rows + lines[table_end:]

    return "".join(result)
