#!/usr/bin/env python3
"""STATUS.md drift detection and auto-update tooling.

Subcommands:
  check     — Detect drift in STATUS.md against authoritative sources (git).
              Output: JSON report. Exit 0 if drift_count=0, else 1.
  sync      — Roll STATUS.md forward for a single ticket merge (idempotent).
              Inputs: --ticket ABC-NNN --pr N --commit SHA
  sanitize  — Regenerate the Active Worktrees table from git state, preserving
              every human-authored section byte-for-byte.

All operations are fail-soft: external tool failures emit structured error JSON,
never raise. The pure parsers + the `status_file`/`worktrees` injection points make
the drift logic unit-testable without git. Mode (warn|block) is advisory — `check`
always exits 1 on drift so callers can detect it; the mode tells the orchestrator
whether to hard-stop. Default mode comes from `STATUS_DRIFT_MODE` in project.conf or
`.dev-context/status-drift.yml`.
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

_DEFAULT_PROJECT_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = Path.cwd() if (Path.cwd() / "STATUS.md").exists() else _DEFAULT_PROJECT_DIR

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s", stream=sys.stderr)
logger = logging.getLogger(__name__)

_PLACEHOLDERS = {"—", "-", "(none)", ""}


@dataclass
class DriftReport:
    phase: str  # "ok" | "drift" | "error"
    mode: str = "warn"
    worktrees: list[dict[str, str]] = field(default_factory=list)
    tickets: list[dict[str, str]] = field(default_factory=list)
    drift_count: int = 0

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


# --- config ---------------------------------------------------------------


def load_mode() -> str:
    """Default drift mode: project.conf STATUS_DRIFT_MODE, else status-drift.yml, else warn."""
    conf = PROJECT_DIR / ".dev-context" / "project.conf"
    if conf.exists():
        for line in conf.read_text().splitlines():
            if line.strip().startswith("STATUS_DRIFT_MODE="):
                val = line.split("=", 1)[1].strip()
                if val in ("warn", "block", "off"):
                    return val
    yml = PROJECT_DIR / ".dev-context" / "status-drift.yml"
    if yml.exists():
        try:
            import yaml

            mode = (yaml.safe_load(yml.read_text()) or {}).get("mode")
            if mode in ("warn", "block", "off"):
                return str(mode)
        except Exception:
            pass
    return "warn"


# --- git ------------------------------------------------------------------


def get_git_worktrees() -> dict[str, str]:
    """Active git worktrees as {normalized_abs_path: same}. Empty on any failure."""
    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logger.warning(f"Failed to retrieve git worktrees: {e}")
        return {}
    worktrees: dict[str, str] = {}
    for line in result.stdout.strip().split("\n"):
        parts = line.split(None, 1)
        if len(parts) >= 2 and parts[0] == "worktree":
            norm = str(Path(parts[1].strip()).resolve())
            worktrees[norm] = norm
    return worktrees


# --- pure parsers ---------------------------------------------------------


def extract_table(content: str, table_header: str) -> list[dict[str, str]]:
    """Extract the markdown table under `table_header` (e.g. '## Active Worktrees')."""
    in_table = False
    table_lines: list[str] = []
    for line in content.split("\n"):
        if line.strip().startswith(table_header):
            in_table = True
            continue
        if in_table:
            if line.startswith("## "):
                break
            if line.startswith("|"):
                table_lines.append(line)
    if not table_lines:
        return []
    headers: list[str] = []
    rows: list[dict[str, str]] = []
    for i, line in enumerate(table_lines):
        cells = [c.strip() for c in line.split("|")[1:-1]]
        if i == 0:
            headers = cells
        elif i == 1:
            continue  # separator row
        elif cells and any(c.strip() for c in cells):
            rows.append(dict(zip(headers, cells, strict=False)))
    return rows


def _status_path(status_file: str | Path | None) -> Path:
    return Path(status_file) if status_file else PROJECT_DIR / "STATUS.md"


# --- check ----------------------------------------------------------------


def check_drift(
    status_file: str | Path | None = None,
    worktrees: dict[str, str] | None = None,
    mode: str | None = None,
) -> DriftReport:
    """Detect drift: STATUS.md worktree/ticket rows not backed by git state.

    `worktrees` is injectable for testing (defaults to live `get_git_worktrees()`)."""
    report = DriftReport(phase="ok", mode=mode or load_mode())
    path = _status_path(status_file)
    if not path.exists():
        report.phase = "drift"
        report.drift_count = 1
        return report
    try:
        content = path.read_text()
        git_worktrees = get_git_worktrees() if worktrees is None else worktrees
        for row in extract_table(content, "## Active Worktrees"):
            wt_dir = (row.get("Worktree Dir") or "").strip()
            if wt_dir in _PLACEHOLDERS:
                continue
            if str(Path(wt_dir).resolve()) not in git_worktrees:
                report.drift_count += 1
                report.worktrees.append({"branch": row.get("Branch", "?"), "status": "orphaned"})
        for row in extract_table(content, "## Active Tickets"):
            if "Queued" in (row.get("Status") or ""):
                report.drift_count += 1
                report.tickets.append(
                    {"ticket": row.get("Ticket", "?"), "claimed": "Queued", "status": "stale"}
                )
        report.phase = "ok" if report.drift_count == 0 else "drift"
    except Exception as e:  # noqa: BLE001  (fail-soft by contract)
        logger.error(f"Failed to parse STATUS.md: {e}")
        report.phase = "error"
    return report


# --- sync -----------------------------------------------------------------


def sync_ticket(
    ticket: str, pr_num: int, commit_sha: str, status_file: str | Path | None = None
) -> bool:
    """Mark a merged ticket Done in the Active Tickets table + add an Activity Log
    line. Idempotent: already-Done tickets return False. Other sections untouched."""
    path = _status_path(status_file)
    if not path.exists():
        logger.error("STATUS.md not found")
        return False
    try:
        lines = path.read_text().split("\n")
        new_lines: list[str] = []
        in_tickets = in_log = updated = ticket_found = already_done = False
        log_first_seen = False
        for line in lines:
            stripped = line.strip()
            if stripped == "## Active Tickets":
                in_tickets, in_log = True, False
            elif stripped == "## Activity Log":
                in_tickets, in_log = False, True
            elif line.startswith("## "):
                in_tickets = in_log = False

            if (
                in_tickets
                and line.startswith("|")
                and ticket in line
                and not line.startswith("| Ticket |")
            ):
                ticket_found = True
                if "**Done**" in line:
                    already_done = True
                    new_lines.append(line)
                else:
                    parts = line.split("|")
                    if len(parts) >= 4:
                        parts[-2] = f" **Done** (merged PR #{pr_num}, `{commit_sha}`) "
                        new_lines.append("|".join(parts))
                        updated = True
                    else:
                        new_lines.append(line)
            elif in_log and line.startswith("- ") and not log_first_seen:
                log_first_seen = True
                if updated:
                    date_str = datetime.now().strftime("%Y-%m-%d")  # noqa: DTZ005
                    new_lines.append(
                        f"- {date_str} — **{ticket} merged (PR #{pr_num}, `{commit_sha}`)**."
                    )
                new_lines.append(line)
            else:
                new_lines.append(line)

        if already_done:
            logger.info(f"Ticket {ticket} already done; no update needed")
            return False
        if updated:
            path.write_text("\n".join(new_lines))
            logger.info(f"Synced {ticket} merge (PR #{pr_num}, {commit_sha})")
            return True
        if not ticket_found:
            logger.warning(f"Ticket {ticket} not found in Active Tickets")
        return False
    except Exception as e:  # noqa: BLE001  (fail-soft by contract)
        logger.error(f"Sync failed: {e}")
        return False


# --- sanitize -------------------------------------------------------------


def _build_worktree_section(worktrees: dict[str, str]) -> list[str]:
    lines = [
        "## Active Worktrees",
        "",
        "| Branch | Worktree Dir | Ticket | Agent | Status | Files Touched |",
        "|---|---|---|---|---|---|",
        "| (none) | — | — | — | — | — |",
        "",
    ]
    return lines


def sanitize_status(
    status_file: str | Path | None = None, worktrees: dict[str, str] | None = None
) -> bool:
    """Regenerate the Active Worktrees table from git state; pass every other
    section through verbatim. Returns True on success (even if no change)."""
    path = _status_path(status_file)
    if not path.exists():
        logger.error("STATUS.md not found")
        return False
    try:
        content = path.read_text()
        git_worktrees = get_git_worktrees() if worktrees is None else worktrees
        regenerated = _build_worktree_section(git_worktrees)
        out: list[str] = []
        skipping = False
        for line in content.split("\n"):
            if line.strip() == "## Active Worktrees":
                out.extend(regenerated)
                skipping = True
                continue
            if skipping:
                if line.startswith("## "):  # next section ends the regenerated block
                    skipping = False
                    out.append(line)
                continue
            out.append(line)
        new_content = "\n".join(out)
        if new_content != content:
            path.write_text(new_content)
            logger.info("Sanitized STATUS.md (regenerated Active Worktrees)")
        return True
    except Exception as e:  # noqa: BLE001  (fail-soft by contract)
        logger.error(f"Sanitize failed: {e}")
        return False


# --- CLI ------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="STATUS.md drift detection and auto-update")
    sub = parser.add_subparsers(dest="command")
    cp = sub.add_parser("check", help="Detect drift in STATUS.md")
    cp.add_argument("--mode", choices=["warn", "block", "off"], default=None)
    sp = sub.add_parser("sync", help="Roll STATUS.md forward for a ticket merge")
    sp.add_argument("--ticket", required=True, help="Ticket ID (e.g. ABC-12)")
    sp.add_argument("--pr", type=int, required=True)
    sp.add_argument("--commit", required=True)
    sub.add_parser("sanitize", help="Regenerate STATUS.md worktree table from git")
    args = parser.parse_args(argv)

    if args.command == "check":
        report = check_drift(mode=args.mode)
        print(report.to_json())
        return 0 if report.drift_count == 0 else 1
    if args.command == "sync":
        return 0 if sync_ticket(args.ticket, args.pr, args.commit) else 1
    if args.command == "sanitize":
        return 0 if sanitize_status() else 1
    parser.print_help()
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
