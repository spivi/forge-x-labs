"""Tests for scripts/sprint_watch.py.

Covers the watch-loop state machine:
- PR detection and reviewer dispatch
- State-file read/write (initial, update, resume)
- Fix-cycle subcase (P2 → fix subagent → re-review)
- Merge-after-clean path (delegates to MergeSupervisor)
- Wave-complete detection (all PRs merged)
- Session-drop resume (state file persists across restarts)
- Max review-cycle enforcement (≤3 cycles → escalate)
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path  # noqa: TC003 — pytest tmp_path fixture uses Path at runtime
from typing import Any
from unittest.mock import patch

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"

# sprint_watch imports its sibling sprint_merge_supervisor via a sys.path seam.
# Load the sibling first so the import inside sprint_watch resolves to the same
# module object the tests can patch.
_sms_spec = importlib.util.spec_from_file_location(
    "sprint_merge_supervisor", _SCRIPTS / "sprint_merge_supervisor.py"
)
_sms = importlib.util.module_from_spec(_sms_spec)
sys.modules["sprint_merge_supervisor"] = _sms
_sms_spec.loader.exec_module(_sms)

_spec = importlib.util.spec_from_file_location("sprint_watch", _SCRIPTS / "sprint_watch.py")
sw = importlib.util.module_from_spec(_spec)
sys.modules["sprint_watch"] = sw  # dataclass + future annotations need this registered
_spec.loader.exec_module(sw)

PRState = sw.PRState
WatchState = sw.WatchState
WatchSupervisor = sw.WatchSupervisor
load_watch_state = sw.load_watch_state
save_watch_state = sw.save_watch_state

# ---------------------------------------------------------------------------
# Helpers / fakes
# ---------------------------------------------------------------------------


def _cp(stdout: str = "", returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")


@dataclass
class FakeCall:
    kind: str
    args: list[str] = field(default_factory=list)
    kwargs: dict[str, Any] = field(default_factory=dict)


class FakeRunner:
    """Deterministic fake CommandRunner for WatchSupervisor tests."""

    def __init__(self, responses: list[subprocess.CompletedProcess[str]]) -> None:
        self._responses = list(responses)
        self._idx = 0
        self.calls: list[FakeCall] = []
        self.sleep_calls: list[float] = []

    def run(
        self,
        args: list[str],
        *,
        check: bool = False,
        capture_output: bool = False,
        cwd: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append(FakeCall(kind="run", args=list(args)))
        if self._idx >= len(self._responses):
            raise RuntimeError(f"FakeRunner: no response #{self._idx}: {args}")
        result = self._responses[self._idx]
        self._idx += 1
        if check and result.returncode != 0:
            raise subprocess.CalledProcessError(result.returncode, args)
        return result

    def sleep(self, seconds: float) -> None:
        self.sleep_calls.append(seconds)
        self.calls.append(FakeCall(kind="sleep"))


# ---------------------------------------------------------------------------
# State-file tests
# ---------------------------------------------------------------------------


def test_load_watch_state_missing_file(tmp_path: Path) -> None:
    """load_watch_state returns an empty WatchState when the file does not exist."""
    state = load_watch_state(tmp_path / "sprint-watch-state.json", wave_tickets=[1, 2])
    assert state.wave_tickets == [1, 2]
    assert state.pr_states == {}


def test_save_and_reload_watch_state(tmp_path: Path) -> None:
    """State file round-trips correctly."""
    path = tmp_path / "state.json"
    state = WatchState(
        wave_tickets=[10, 20],
        pr_states={
            42: PRState(ticket=10, pr=42, cycle=2, status="clean"),
        },
    )
    save_watch_state(path, state)
    reloaded = load_watch_state(path, wave_tickets=[10, 20])
    assert reloaded.wave_tickets == [10, 20]
    assert reloaded.pr_states[42].status == "clean"
    assert reloaded.pr_states[42].cycle == 2


def test_save_watch_state_creates_parent_dirs(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "dir" / "state.json"
    state = WatchState(wave_tickets=[1])
    save_watch_state(path, state)
    assert path.exists()


# ---------------------------------------------------------------------------
# WatchState helpers
# ---------------------------------------------------------------------------


def test_wave_complete_when_all_merged() -> None:
    state = WatchState(
        wave_tickets=[1, 2],
        pr_states={
            10: PRState(ticket=1, pr=10, status="merged"),
            20: PRState(ticket=2, pr=20, status="merged"),
        },
    )
    assert state.wave_complete(total_agents=2)


def test_wave_not_complete_pending_agent() -> None:
    """Wave is not complete while agents still haven't opened PRs yet."""
    state = WatchState(
        wave_tickets=[1, 2],
        pr_states={
            10: PRState(ticket=1, pr=10, status="merged"),
        },
    )
    assert not state.wave_complete(total_agents=2)


def test_wave_not_complete_pr_in_review() -> None:
    state = WatchState(
        wave_tickets=[1, 2],
        pr_states={
            10: PRState(ticket=1, pr=10, status="merged"),
            20: PRState(ticket=2, pr=20, status="in_flight", cycle=1),
        },
    )
    assert not state.wave_complete(total_agents=2)


# ---------------------------------------------------------------------------
# WatchSupervisor.list_open_prs  (gh pr list call)
# ---------------------------------------------------------------------------


def test_list_open_prs_returns_numbers(tmp_path: Path) -> None:
    prs_json = json.dumps([{"number": 42}, {"number": 99}])
    runner = FakeRunner([_cp(stdout=prs_json)])
    sup = WatchSupervisor(
        wave_tickets=[10, 20],
        worktree_root=tmp_path,
        state_path=tmp_path / "state.json",
        runner=runner,
        poll_interval=0,
    )
    result = sup.list_open_prs()
    assert result == [42, 99]


def test_list_open_prs_empty_on_gh_failure(tmp_path: Path) -> None:
    runner = FakeRunner([_cp(stdout="", returncode=1)])
    sup = WatchSupervisor(
        wave_tickets=[10],
        worktree_root=tmp_path,
        state_path=tmp_path / "state.json",
        runner=runner,
        poll_interval=0,
    )
    result = sup.list_open_prs()
    assert result == []


# ---------------------------------------------------------------------------
# WatchSupervisor._get_pr_ticket  (gh pr view → body parsing)
# ---------------------------------------------------------------------------


def test_get_pr_ticket_from_body(tmp_path: Path) -> None:
    pr_body = json.dumps({"body": "Implements #42\n\nSome content"})
    runner = FakeRunner([_cp(stdout=pr_body)])
    sup = WatchSupervisor(
        wave_tickets=[42],
        worktree_root=tmp_path,
        state_path=tmp_path / "state.json",
        runner=runner,
        poll_interval=0,
    )
    ticket = sup._get_pr_ticket(pr_number=100)
    assert ticket == 42


def test_get_pr_ticket_not_in_wave_returns_none(tmp_path: Path) -> None:
    """PR that closes a ticket NOT in this wave should be skipped."""
    pr_body = json.dumps({"body": "Closes #999"})
    runner = FakeRunner([_cp(stdout=pr_body)])
    sup = WatchSupervisor(
        wave_tickets=[42],
        worktree_root=tmp_path,
        state_path=tmp_path / "state.json",
        runner=runner,
        poll_interval=0,
    )
    ticket = sup._get_pr_ticket(pr_number=100)
    assert ticket is None


# ---------------------------------------------------------------------------
# WatchSupervisor._dispatch_reviewer  (Task subagent call check)
# ---------------------------------------------------------------------------


def test_dispatch_reviewer_updates_state(tmp_path: Path) -> None:
    """After dispatching, state transitions to in_flight."""
    runner = FakeRunner([])
    sup = WatchSupervisor(
        wave_tickets=[10],
        worktree_root=tmp_path,
        state_path=tmp_path / "state.json",
        runner=runner,
        poll_interval=0,
    )
    state = WatchState(wave_tickets=[10])

    # Patch the Task subagent call (it spawns a real Claude Task in prod)
    pass_verdict = {"verdict": "PASS", "counts": {"p1": 0, "p2": 0, "p3": 0}}
    with patch.object(sup, "_spawn_reviewer_task", return_value=pass_verdict) as mock_spawn:
        sup._dispatch_reviewer(pr=55, ticket=10, cycle=1, state=state)
        mock_spawn.assert_called_once()

    assert 55 in state.pr_states
    assert state.pr_states[55].status == "clean"


def test_dispatch_reviewer_p2_triggers_fix_cycle(tmp_path: Path) -> None:
    """A P2 finding triggers a fix subagent and increments the cycle count."""
    runner = FakeRunner([])
    sup = WatchSupervisor(
        wave_tickets=[10],
        worktree_root=tmp_path,
        state_path=tmp_path / "state.json",
        runner=runner,
        poll_interval=0,
    )
    state = WatchState(wave_tickets=[10])

    verdict_cycle1 = {"verdict": "FAIL", "counts": {"p1": 0, "p2": 1, "p3": 0}}
    verdict_cycle2 = {"verdict": "PASS", "counts": {"p1": 0, "p2": 0, "p3": 0}}

    with (
        patch.object(sup, "_spawn_reviewer_task", side_effect=[verdict_cycle1, verdict_cycle2]),
        patch.object(sup, "_spawn_fix_task", return_value=None),
        patch.object(sup, "_record_and_audit", return_value=None),
    ):
        sup._dispatch_reviewer(pr=55, ticket=10, cycle=1, state=state)

    assert state.pr_states[55].cycle == 2
    assert state.pr_states[55].status == "clean"


def test_dispatch_reviewer_p1_blocks_merge(tmp_path: Path) -> None:
    """A P1 finding after max cycles sets status to escalated (no merge)."""
    runner = FakeRunner([])
    sup = WatchSupervisor(
        wave_tickets=[10],
        worktree_root=tmp_path,
        state_path=tmp_path / "state.json",
        runner=runner,
        poll_interval=0,
        max_review_cycles=1,
    )
    state = WatchState(wave_tickets=[10])

    verdict_p1 = {"verdict": "FAIL", "counts": {"p1": 1, "p2": 0, "p3": 0}}

    with (
        patch.object(sup, "_spawn_reviewer_task", return_value=verdict_p1),
        patch.object(sup, "_record_and_audit", return_value=None),
    ):
        sup._dispatch_reviewer(pr=55, ticket=10, cycle=1, state=state)

    assert state.pr_states[55].status == "escalated"


# ---------------------------------------------------------------------------
# WatchSupervisor._merge_clean_prs  (delegates to MergeSupervisor)
# ---------------------------------------------------------------------------


def test_merge_clean_prs_calls_supervisor(tmp_path: Path) -> None:
    runner = FakeRunner([])
    sup = WatchSupervisor(
        wave_tickets=[10],
        worktree_root=tmp_path,
        state_path=tmp_path / "state.json",
        runner=runner,
        poll_interval=0,
    )
    state = WatchState(
        wave_tickets=[10],
        pr_states={55: PRState(ticket=10, pr=55, status="clean")},
    )

    with patch.object(sw, "MergeSupervisor") as mock_supervisor_cls:
        mock_instance = mock_supervisor_cls.return_value
        mock_instance.run.return_value = None
        sup._merge_clean_prs(state)
        mock_supervisor_cls.assert_called_once()
        mock_instance.run.assert_called_once()

    assert state.pr_states[55].status == "merged"


def test_merge_clean_prs_skips_non_clean(tmp_path: Path) -> None:
    runner = FakeRunner([])
    sup = WatchSupervisor(
        wave_tickets=[10, 20],
        worktree_root=tmp_path,
        state_path=tmp_path / "state.json",
        runner=runner,
        poll_interval=0,
    )
    state = WatchState(
        wave_tickets=[10, 20],
        pr_states={
            55: PRState(ticket=10, pr=55, status="in_flight", cycle=1),
            66: PRState(ticket=20, pr=66, status="clean"),
        },
    )

    with patch.object(sw, "MergeSupervisor") as mock_supervisor_cls:
        mock_instance = mock_supervisor_cls.return_value
        mock_instance.run.return_value = None
        sup._merge_clean_prs(state)
        mock_supervisor_cls.assert_called_once()  # only one PR was clean

    assert state.pr_states[55].status == "in_flight"
    assert state.pr_states[66].status == "merged"


# ---------------------------------------------------------------------------
# WatchSupervisor.run — wave-complete fast path
# ---------------------------------------------------------------------------


def test_run_exits_when_wave_complete_on_resume(tmp_path: Path) -> None:
    """If the state file shows all PRs merged already, run() returns immediately."""
    state = WatchState(
        wave_tickets=[10],
        pr_states={55: PRState(ticket=10, pr=55, status="merged")},
    )
    state_path = tmp_path / "state.json"
    save_watch_state(state_path, state)

    runner = FakeRunner([])
    sup = WatchSupervisor(
        wave_tickets=[10],
        worktree_root=tmp_path,
        state_path=state_path,
        runner=runner,
        poll_interval=0,
    )
    # Should not raise and should not make any runner calls
    sup.run(total_agents=1)
    assert runner._idx == 0


def test_run_resumes_in_flight_pr(tmp_path: Path) -> None:
    """Session-drop resume re-dispatches in-flight PRs via _detect_new_prs.

    Scenario:
      - State file has PR #55 (ticket #10) stuck in 'in_flight' (session dropped
        while reviewer was running).
      - On resume, _reset_in_flight removes #55 from pr_states.
      - The next poll's _detect_new_prs sees #55 as new and re-dispatches the
        reviewer.
      - The reviewer returns PASS → PR is marked clean → merged → wave complete.
    """
    # Write a state file with one in-flight PR (simulates a dropped session).
    state = WatchState(
        wave_tickets=[10],
        pr_states={55: PRState(ticket=10, pr=55, status="in_flight", cycle=2)},
    )
    state_path = tmp_path / "state.json"
    save_watch_state(state_path, state)

    # Runner: list_open_prs returns PR #55; pr view body references ticket #10.
    prs_json = json.dumps([{"number": 55}])
    pr_body_json = json.dumps({"body": "Implements #10"})
    pr_diff = ""  # no arch files → sonnet reviewer

    runner = FakeRunner(
        [
            _cp(stdout=prs_json),  # gh pr list (first poll)
            _cp(stdout=pr_body_json),  # gh pr view 55 --json body
            _cp(stdout=pr_diff),  # gh pr diff 55 --name-only (model selection)
        ]
    )

    sup = WatchSupervisor(
        wave_tickets=[10],
        worktree_root=tmp_path,
        state_path=state_path,
        runner=runner,
        poll_interval=0,
    )

    pass_verdict = {"verdict": "PASS", "counts": {"p1": 0, "p2": 0, "p3": 0}}
    reviewer_calls: list[dict[str, object]] = []

    def fake_reviewer(pr: int, ticket: int, cycle: int) -> dict[str, object]:
        reviewer_calls.append({"pr": pr, "ticket": ticket, "cycle": cycle})
        return pass_verdict

    with (
        patch.object(sup, "_spawn_reviewer_task", side_effect=fake_reviewer),
        patch.object(sup, "_record_and_audit", return_value=None),
        patch.object(sw, "MergeSupervisor") as mock_merge_cls,
    ):
        mock_merge_cls.return_value.run.return_value = None
        sup.run(total_agents=1)

    # Reviewer must have been dispatched exactly once (re-dispatched from cycle 1).
    assert len(reviewer_calls) == 1, f"Expected 1 reviewer call, got {reviewer_calls}"
    assert reviewer_calls[0]["pr"] == 55
    assert reviewer_calls[0]["cycle"] == 1  # reset to cycle 1 on resume
    assert reviewer_calls[0]["ticket"] == 10

    # PR should have been merged at the end.
    reloaded = load_watch_state(state_path, wave_tickets=[10])
    assert reloaded.pr_states[55].status == "merged"
