"""Tests for scripts/sprint_merge_supervisor.py.

Covers every branch of the state machine and the pre-emptive rebase helper.

Case table under test:
  CLEAN / UNSTABLE  → merge and return
  BEHIND            → git pull --rebase + git push --force-with-lease, then retry
  BEHIND (dirty)    → escalate (don't clobber operator work)
  BEHIND (no wt)    → escalate (worktree_path not set)
  BLOCKED (stale)   → empty-commit workaround, then retry
  BLOCKED (other)   → escalate
  DIRTY             → escalate immediately
  UNKNOWN           → sleep and retry
  *                 → escalate on unexpected state
  budget exhausted  → escalate after max_attempts
  preemptive_rebase → rebase all worktrees in list; skip dirty ones
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
_spec = importlib.util.spec_from_file_location(
    "sprint_merge_supervisor", _SCRIPTS / "sprint_merge_supervisor.py"
)
sms = importlib.util.module_from_spec(_spec)
sys.modules["sprint_merge_supervisor"] = sms  # dataclass + future annotations need this
_spec.loader.exec_module(sms)

EscalateError = sms.EscalateError
MergeSupervisor = sms.MergeSupervisor
preemptive_rebase = sms.preemptive_rebase

# ---------------------------------------------------------------------------
# Fake CommandRunner
# ---------------------------------------------------------------------------


@dataclass
class FakeCall:
    """Record of a single run() or sleep() invocation."""

    kind: str  # "run" or "sleep"
    args: list[str] = field(default_factory=list)
    kwargs: dict[str, Any] = field(default_factory=dict)


class FakeRunner:
    """Injectable fake that returns pre-programmed responses for each run() call."""

    def __init__(self, responses: list[subprocess.CompletedProcess[str]]) -> None:
        self.responses = list(responses)
        self._response_idx = 0
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
        if self._response_idx >= len(self.responses):
            raise RuntimeError(
                f"FakeRunner: no response configured for call #{self._response_idx}: {args}"
            )
        result = self.responses[self._response_idx]
        self._response_idx += 1
        if check and result.returncode != 0:
            raise subprocess.CalledProcessError(result.returncode, args)
        return result

    def sleep(self, seconds: float) -> None:
        self.sleep_calls.append(seconds)
        self.calls.append(FakeCall(kind="sleep"))


# ---------------------------------------------------------------------------
# Helpers for building fake responses
# ---------------------------------------------------------------------------


def ok(stdout: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


def fail(stderr: str = "error") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr=stderr)


def state_resp(state: str) -> subprocess.CompletedProcess[str]:
    """Fake response for `gh pr view --json mergeStateStatus --jq .mergeStateStatus`."""
    return ok(state)


def checks_resp(checks: list[dict[str, str]]) -> subprocess.CompletedProcess[str]:
    return ok(json.dumps(checks))


def pr_dump_resp() -> subprocess.CompletedProcess[str]:
    return ok('{"number":123,"mergeStateStatus":"CLEAN"}')


# ---------------------------------------------------------------------------
# _merge_method (project.conf parsing)
# ---------------------------------------------------------------------------


def test_merge_method_defaults_to_merge() -> None:
    """The template project.conf ships MERGE_METHOD=merge."""
    assert sms._merge_method() == "merge"


# ---------------------------------------------------------------------------
# CLEAN → merge and return
# ---------------------------------------------------------------------------


def test_clean_merges_immediately() -> None:
    runner = FakeRunner(
        [
            state_resp("CLEAN"),  # _get_merge_state()
            ok(),  # gh pr merge --merge --delete-branch
        ]
    )
    sup = MergeSupervisor(pr_number=123, runner=runner)
    sup.run()

    assert "merged" in sup._actions_taken
    # Verify gh pr merge used the configured method (--merge) and delete-branch.
    merge_call = runner.calls[1]
    assert "--merge" in merge_call.args
    assert "--delete-branch" in merge_call.args


def test_unstable_merges_immediately() -> None:
    runner = FakeRunner(
        [
            state_resp("UNSTABLE"),
            ok(),
        ]
    )
    sup = MergeSupervisor(pr_number=42, runner=runner)
    sup.run()
    assert "merged" in sup._actions_taken


# ---------------------------------------------------------------------------
# BEHIND → rebase + push, then retry to CLEAN
# ---------------------------------------------------------------------------


def test_behind_triggers_rebase_then_merges() -> None:
    runner = FakeRunner(
        [
            state_resp("BEHIND"),  # attempt 1: mergeStateStatus
            ok(""),  # git status --porcelain (clean)
            ok(),  # git fetch origin
            ok(),  # git pull --rebase origin master
            ok(),  # git push --force-with-lease
            state_resp("CLEAN"),  # attempt 2: re-check after sleep
            ok(),  # gh pr merge
        ]
    )
    wt = Path("/fake/worktree")
    sup = MergeSupervisor(pr_number=99, worktree_path=wt, runner=runner)
    sup.run()

    assert "rebase+push" in sup._actions_taken
    assert "merged" in sup._actions_taken
    # A sleep should have been issued between rebase and re-check
    assert len(runner.sleep_calls) == 1
    # The rebase targets origin/master (template default branch).
    rebase_call = runner.calls[3]
    assert rebase_call.args == ["git", "pull", "--rebase", "origin", "master"]


def test_behind_escalates_when_no_worktree_path() -> None:
    runner = FakeRunner(
        [
            state_resp("BEHIND"),
            pr_dump_resp(),  # _dump_pr_state() inside _escalate
        ]
    )
    sup = MergeSupervisor(pr_number=99, worktree_path=None, runner=runner)
    with pytest.raises(EscalateError) as exc_info:
        sup.run()
    assert exc_info.value.state == "BEHIND"
    assert "worktree_path not set" in exc_info.value.reason


def test_behind_escalates_on_dirty_worktree() -> None:
    runner = FakeRunner(
        [
            state_resp("BEHIND"),
            ok("M  some_file.py"),  # git status --porcelain → dirty
            pr_dump_resp(),
        ]
    )
    sup = MergeSupervisor(pr_number=99, worktree_path=Path("/wt"), runner=runner)
    with pytest.raises(EscalateError) as exc_info:
        sup.run()
    assert exc_info.value.state == "BEHIND"
    assert "uncommitted changes" in exc_info.value.reason


def test_behind_escalates_on_rebase_failure() -> None:
    runner = FakeRunner(
        [
            state_resp("BEHIND"),
            ok(""),  # git status --porcelain
            ok(),  # git fetch origin
            fail("conflict"),  # git pull --rebase → fails
            pr_dump_resp(),
        ]
    )
    sup = MergeSupervisor(pr_number=99, worktree_path=Path("/wt"), runner=runner)
    with pytest.raises(EscalateError) as exc_info:
        sup.run()
    assert exc_info.value.state == "BEHIND"
    assert "rebase failed" in exc_info.value.reason


def test_behind_escalates_on_push_failure() -> None:
    runner = FakeRunner(
        [
            state_resp("BEHIND"),
            ok(""),  # git status --porcelain
            ok(),  # git fetch
            ok(),  # git pull --rebase OK
            fail("remote rejected"),  # git push --force-with-lease fails
            pr_dump_resp(),
        ]
    )
    sup = MergeSupervisor(pr_number=99, worktree_path=Path("/wt"), runner=runner)
    with pytest.raises(EscalateError) as exc_info:
        sup.run()
    assert exc_info.value.state == "BEHIND"
    assert "force-with-lease failed" in exc_info.value.reason


# ---------------------------------------------------------------------------
# BLOCKED (stale FAILURE) → empty-commit workaround
# ---------------------------------------------------------------------------


def test_blocked_stale_failure_pushes_empty_commit_then_merges() -> None:
    stale_check = [
        {
            "name": "ci/test",
            "state": "COMPLETED",
            "conclusion": "FAILURE",
            "startedAt": "2020-01-01T00:00:00Z",
        }
    ]

    runner = FakeRunner(
        [
            state_resp("BLOCKED"),  # attempt 1
            checks_resp(stale_check),  # gh pr checks
            ok("abc1234"),  # git rev-parse HEAD
            ok("1700000000"),  # git log --format=%ct (commit ts > check ts)
            ok(),  # git commit --allow-empty
            ok(),  # git push (after empty commit)
            state_resp("CLEAN"),  # attempt 2
            ok(),  # gh pr merge
        ]
    )
    wt = Path("/fake/wt")
    sup = MergeSupervisor(pr_number=55, worktree_path=wt, runner=runner)
    sup.run()

    assert "empty-commit" in sup._actions_taken
    assert "merged" in sup._actions_taken


def test_blocked_stale_failure_no_worktree_escalates() -> None:
    """When worktree is None, subcase (a) is skipped; falls through to escalate."""
    stale_check = [
        {
            "name": "ci/test",
            "state": "COMPLETED",
            "conclusion": "FAILURE",
            "startedAt": "2020-01-01T00:00:00Z",
        }
    ]

    runner = FakeRunner(
        [
            state_resp("BLOCKED"),
            checks_resp(stale_check),  # checks present, but no worktree
            pr_dump_resp(),  # _dump_pr_state in _escalate
        ]
    )
    sup = MergeSupervisor(pr_number=55, worktree_path=None, runner=runner)
    with pytest.raises(EscalateError) as exc_info:
        sup.run()
    assert exc_info.value.state == "BLOCKED"
    assert "could not be auto-resolved" in exc_info.value.reason


def test_blocked_escalates_when_no_known_subcase() -> None:
    """BLOCKED with no stale checks → escalate."""
    runner = FakeRunner(
        [
            state_resp("BLOCKED"),
            checks_resp([]),
            pr_dump_resp(),
        ]
    )
    sup = MergeSupervisor(pr_number=33, runner=runner)
    with pytest.raises(EscalateError) as exc_info:
        sup.run()
    assert exc_info.value.state == "BLOCKED"
    assert "could not be auto-resolved" in exc_info.value.reason


# ---------------------------------------------------------------------------
# DIRTY → immediate escalation
# ---------------------------------------------------------------------------


def test_dirty_escalates_immediately() -> None:
    runner = FakeRunner(
        [
            state_resp("DIRTY"),
            pr_dump_resp(),
        ]
    )
    sup = MergeSupervisor(pr_number=11, runner=runner)
    with pytest.raises(EscalateError) as exc_info:
        sup.run()
    assert exc_info.value.state == "DIRTY"
    assert "conflict" in exc_info.value.reason.lower()


# ---------------------------------------------------------------------------
# UNKNOWN → sleep then retry
# ---------------------------------------------------------------------------


def test_unknown_sleeps_then_retries_to_clean() -> None:
    runner = FakeRunner(
        [
            state_resp("UNKNOWN"),  # attempt 1
            state_resp("CLEAN"),  # attempt 2
            ok(),  # gh pr merge
        ]
    )
    sup = MergeSupervisor(pr_number=22, runner=runner)
    sup.run()

    assert len(runner.sleep_calls) == 1
    assert runner.sleep_calls[0] == 30  # UNKNOWN_SLEEP_SECONDS
    assert "merged" in sup._actions_taken


# ---------------------------------------------------------------------------
# Unexpected state → escalate
# ---------------------------------------------------------------------------


def test_unexpected_state_escalates() -> None:
    runner = FakeRunner(
        [
            state_resp("TOTALLY_NEW_STATE"),
            pr_dump_resp(),
        ]
    )
    sup = MergeSupervisor(pr_number=44, runner=runner)
    with pytest.raises(EscalateError) as exc_info:
        sup.run()
    assert "TOTALLY_NEW_STATE" in exc_info.value.reason


# ---------------------------------------------------------------------------
# Budget exhaustion → escalate after max_attempts
# ---------------------------------------------------------------------------


def test_budget_exhausted_after_max_attempts() -> None:
    # Keep returning UNKNOWN forever so the budget runs out
    responses = [state_resp("UNKNOWN")] * 5  # max_attempts=5
    responses.append(pr_dump_resp())  # _dump_pr_state in the budget check
    runner = FakeRunner(responses)
    sup = MergeSupervisor(pr_number=66, max_attempts=5, runner=runner)
    with pytest.raises(EscalateError) as exc_info:
        sup.run()
    assert exc_info.value.state == "BUDGET_EXHAUSTED"
    assert "max_attempts=5" in exc_info.value.reason


def test_budget_exhausted_single_attempt() -> None:
    runner = FakeRunner(
        [
            state_resp("UNKNOWN"),
            pr_dump_resp(),
        ]
    )
    sup = MergeSupervisor(pr_number=1, max_attempts=1, runner=runner)
    with pytest.raises(EscalateError) as exc_info:
        sup.run()
    assert exc_info.value.state == "BUDGET_EXHAUSTED"


# ---------------------------------------------------------------------------
# Merge failure even on CLEAN state
# ---------------------------------------------------------------------------


def test_merge_failure_on_clean_state_escalates() -> None:
    runner = FakeRunner(
        [
            state_resp("CLEAN"),  # mergeStateStatus
            fail("merge conflict"),  # gh pr merge fails
            state_resp("DIRTY"),  # re-check state after failed merge
            pr_dump_resp(),  # dump state
        ]
    )
    sup = MergeSupervisor(pr_number=123, runner=runner)
    with pytest.raises(EscalateError) as exc_info:
        sup.run()
    assert "gh pr merge failed" in exc_info.value.reason


# ---------------------------------------------------------------------------
# gh pr view failure → UNKNOWN fallback
# ---------------------------------------------------------------------------


def test_gh_view_failure_returns_unknown() -> None:
    runner = FakeRunner(
        [
            fail("rate limited"),  # gh pr view fails → UNKNOWN
            state_resp("CLEAN"),  # next attempt: OK
            ok(),  # gh pr merge
        ]
    )
    sup = MergeSupervisor(pr_number=5, runner=runner)
    sup.run()
    assert "merged" in sup._actions_taken


# ---------------------------------------------------------------------------
# Pre-emptive rebase helper
# ---------------------------------------------------------------------------


def test_preemptive_rebase_ok() -> None:
    wt_a = Path("/wt/a")
    wt_b = Path("/wt/b")

    runner = FakeRunner(
        [
            ok(""),  # git status wt_a
            ok(),  # git fetch wt_a
            ok(),  # git pull --rebase wt_a
            ok(),  # git push wt_a
            ok(""),  # git status wt_b
            ok(),  # git fetch wt_b
            ok(),  # git pull --rebase wt_b
            ok(),  # git push wt_b
        ]
    )
    results = preemptive_rebase([wt_a, wt_b], runner=runner)
    assert results[wt_a] == "ok"
    assert results[wt_b] == "ok"
    # Pre-emptive rebase targets origin/master.
    assert runner.calls[2].args == ["git", "pull", "--rebase", "origin", "master"]


def test_preemptive_rebase_skips_dirty_worktree() -> None:
    wt_a = Path("/wt/a")
    wt_b = Path("/wt/b")

    runner = FakeRunner(
        [
            ok("M  foo.py"),  # wt_a is dirty → skip
            ok(""),  # wt_b clean
            ok(),  # git fetch wt_b
            ok(),  # git pull wt_b
            ok(),  # git push wt_b
        ]
    )
    results = preemptive_rebase([wt_a, wt_b], runner=runner)
    assert results[wt_a] == "dirty"
    assert results[wt_b] == "ok"


def test_preemptive_rebase_records_error_on_rebase_failure() -> None:
    wt = Path("/wt/x")
    runner = FakeRunner(
        [
            ok(""),  # git status
            ok(),  # git fetch
            fail("conflict!!"),  # git pull --rebase fails
        ]
    )
    results = preemptive_rebase([wt], runner=runner)
    assert results[wt].startswith("error:")
    assert "conflict" in results[wt]


def test_preemptive_rebase_records_error_on_push_failure() -> None:
    wt = Path("/wt/y")
    runner = FakeRunner(
        [
            ok(""),
            ok(),
            ok(),  # rebase ok
            fail("rejected"),  # push fails
        ]
    )
    results = preemptive_rebase([wt], runner=runner)
    assert results[wt].startswith("error:")
    assert "rejected" in results[wt]


def test_preemptive_rebase_empty_list() -> None:
    runner = FakeRunner([])
    results = preemptive_rebase([], runner=runner)
    assert results == {}
