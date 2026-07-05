"""Tests for scripts/status_drift.py.

The drift logic is exercised with injected `status_file` + `worktrees`, so it runs
with no git and no real STATUS.md. sync/sanitize operate on tmp files.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
_spec = importlib.util.spec_from_file_location("status_drift", _SCRIPTS / "status_drift.py")
sd = importlib.util.module_from_spec(_spec)
sys.modules["status_drift"] = sd  # dataclass + future annotations need this registered
_spec.loader.exec_module(sd)

WORKTREE_ROW = (
    "## Active Worktrees\n\n"
    "| Branch | Worktree Dir | Ticket | Agent | Status | Files Touched |\n"
    "|---|---|---|---|---|---|\n"
    "| feat/x | {wt} | ABC-1 | dev | in-progress | a.py |\n"
)
PLACEHOLDER = (
    "## Active Worktrees\n\n"
    "| Branch | Worktree Dir | Ticket | Agent | Status | Files Touched |\n"
    "|---|---|---|---|---|---|\n"
    "| (none) | — | — | — | — | — |\n"
)
SYNC_STATUS = (
    "## Active Tickets\n\n"
    "| Ticket | Milestone | Status |\n"
    "|---|---|---|\n"
    "| ABC-1 | M1 | In Progress |\n\n"
    "## Activity Log\n\n"
    "- 2026-01-01 — seeded.\n"
)


# --- extract_table --------------------------------------------------------


def test_extract_table_parses_rows():
    rows = sd.extract_table(PLACEHOLDER, "## Active Worktrees")
    assert rows == [
        {
            "Branch": "(none)",
            "Worktree Dir": "—",
            "Ticket": "—",
            "Agent": "—",
            "Status": "—",
            "Files Touched": "—",
        }
    ]


def test_extract_table_absent_returns_empty():
    assert sd.extract_table("# no tables here", "## Active Worktrees") == []


# --- check_drift ----------------------------------------------------------


def test_check_drift_orphaned_worktree(tmp_path):
    wt = tmp_path / "wt"
    status = tmp_path / "STATUS.md"
    status.write_text(WORKTREE_ROW.format(wt=str(wt)))
    report = sd.check_drift(status_file=status, worktrees={}, mode="warn")  # git knows none
    assert report.drift_count == 1
    assert report.phase == "drift"
    assert report.worktrees[0]["status"] == "orphaned"


def test_check_drift_clean_when_worktree_known(tmp_path):
    wt = tmp_path / "wt"
    status = tmp_path / "STATUS.md"
    status.write_text(WORKTREE_ROW.format(wt=str(wt)))
    known = {str(wt.resolve()): str(wt.resolve())}
    report = sd.check_drift(status_file=status, worktrees=known, mode="warn")
    assert report.drift_count == 0
    assert report.phase == "ok"


def test_check_drift_skips_placeholder_row(tmp_path):
    status = tmp_path / "STATUS.md"
    status.write_text(PLACEHOLDER)
    report = sd.check_drift(status_file=status, worktrees={}, mode="warn")
    assert report.drift_count == 0


def test_check_drift_flags_queued_ticket(tmp_path):
    status = tmp_path / "STATUS.md"
    status.write_text(
        "## Active Tickets\n\n| Ticket | Milestone | Status |\n|---|---|---|\n"
        "| ABC-9 | M1 | Queued |\n"
    )
    report = sd.check_drift(status_file=status, worktrees={}, mode="warn")
    assert report.drift_count == 1
    assert report.tickets[0]["ticket"] == "ABC-9"


def test_check_drift_missing_status_file(tmp_path):
    report = sd.check_drift(status_file=tmp_path / "nope.md", worktrees={}, mode="warn")
    assert report.drift_count == 1
    assert report.phase == "drift"


def test_report_to_json_includes_mode():
    report = sd.DriftReport(phase="ok", mode="block")
    assert '"mode": "block"' in report.to_json()


# --- sync_ticket ----------------------------------------------------------


def test_sync_marks_ticket_done_and_logs(tmp_path):
    status = tmp_path / "STATUS.md"
    status.write_text(SYNC_STATUS)
    assert sd.sync_ticket("ABC-1", 42, "abc123", status_file=status) is True
    text = status.read_text()
    assert "**Done** (merged PR #42, `abc123`)" in text
    assert "ABC-1 merged (PR #42, `abc123`)" in text  # activity-log entry prepended
    # Idempotent: a second sync of the already-Done ticket is a no-op.
    assert sd.sync_ticket("ABC-1", 42, "abc123", status_file=status) is False


def test_sync_ticket_not_found(tmp_path):
    status = tmp_path / "STATUS.md"
    status.write_text(SYNC_STATUS)
    assert sd.sync_ticket("ZZZ-9", 1, "deadbeef", status_file=status) is False


def test_sync_missing_status_file(tmp_path):
    assert sd.sync_ticket("ABC-1", 1, "x", status_file=tmp_path / "nope.md") is False


# --- sanitize -------------------------------------------------------------


def test_sanitize_preserves_human_sections(tmp_path):
    status = tmp_path / "STATUS.md"
    status.write_text(
        "## Recent Achievements\n\n- shipped X\n\n" + PLACEHOLDER + "\n## Next Steps\n\n- do Y\n"
    )
    assert sd.sanitize_status(status_file=status, worktrees={}) is True
    text = status.read_text()
    assert "- shipped X" in text  # human section preserved
    assert "- do Y" in text
    assert "## Active Worktrees" in text


# --- config ---------------------------------------------------------------


def test_load_mode_returns_valid_value():
    assert sd.load_mode() in ("warn", "block", "off")
