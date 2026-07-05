"""Sprint merge supervisor: handles ALL non-CLEAN mergeStateStatus values.

A full state-machine that acts on every non-CLEAN mergeStateStatus rather than
passively waiting for a branch-protection retry loop:

  CLEAN | UNSTABLE   -> gh pr merge --<method> --delete-branch ; done
  BEHIND             -> git pull --rebase origin master && git push --force-with-lease
  BLOCKED            -> diagnose subcases:
                          (a) stale FAILURE on same SHA -> empty-commit workaround
                          (b) required-check rename / branch protection / review gate
                              -> escalate
  DIRTY              -> escalate (merge conflict needs human)
  UNKNOWN            -> sleep 30 ; retry (GitHub recomputing)
  *                  -> escalate (unexpected state)

The merge method (``merge`` | ``squash`` | ``rebase``) is read from
``.dev-context/project.conf`` (``MERGE_METHOD=``), defaulting to ``merge``.

Per-PR attempt budget defaults to MAX_ATTEMPTS=5; escalate if exceeded.

Usage (from the orchestrator / SKILL.md):

  from scripts.sprint_merge_supervisor import MergeSupervisor, EscalateError

  supervisor = MergeSupervisor(
      pr_number=123,
      worktree_path=Path(".worktrees/<ticket>"),
  )
  supervisor.run()   # raises EscalateError if human intervention is needed

Callable from the CLI:

  python scripts/sprint_merge_supervisor.py --pr 123 --worktree .worktrees/<ticket>

``worktree_path`` is a plain parameter — pass any absolute or relative path.
The in-clone ``.worktrees/<ticket>`` layout (gitignored) works on both the local
CLI and a cloud sandbox that has no sibling filesystem. Projects using the
sibling worktree layout (``../<project>--<ticket>``) can pass that path directly.
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_ATTEMPTS: int = 5
UNKNOWN_SLEEP_SECONDS: int = 30
BEHIND_SLEEP_SECONDS: int = 5  # short pause after rebase+push before re-check

# Default branch the template merges into / rebases on.
DEFAULT_BRANCH: str = "master"

# States that are immediately mergeable (no action needed before gh pr merge)
MERGEABLE_STATES: frozenset[str] = frozenset({"CLEAN", "UNSTABLE"})

# States that mean GitHub is still computing (safe to sleep and retry)
RESOLVING_STATES: frozenset[str] = frozenset({"UNKNOWN"})

# project.conf location (repo root is the parent of scripts/).
_PROJECT_CONF: Path = Path(__file__).resolve().parents[1] / ".dev-context" / "project.conf"


def _merge_method() -> str:
    """Return the merge method from project.conf ``MERGE_METHOD=``.

    Values: ``merge`` | ``squash`` | ``rebase``; defaults to ``merge`` when the
    key is absent, unrecognised, or project.conf does not exist.
    """
    default = "merge"
    if not _PROJECT_CONF.exists():
        return default
    for line in _PROJECT_CONF.read_text().splitlines():
        if line.strip().startswith("MERGE_METHOD="):
            value = line.split("=", 1)[1].strip().lower()
            if value in ("merge", "squash", "rebase"):
                return value
            return default
    return default


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class EscalateError(RuntimeError):
    """Raised when human intervention is required.

    Attributes:
        pr_number: The PR that is stuck.
        state: The mergeStateStatus at escalation time.
        reason: Human-readable explanation.
        state_dump: Optional raw JSON from ``gh pr view``.
    """

    def __init__(
        self,
        pr_number: int,
        state: str,
        reason: str,
        state_dump: str = "",
    ) -> None:
        self.pr_number = pr_number
        self.state = state
        self.reason = reason
        self.state_dump = state_dump
        super().__init__(
            f"PR #{pr_number} requires human intervention: {reason} (mergeStateStatus={state})"
        )


# ---------------------------------------------------------------------------
# Shell / GitHub call abstractions (injected for testing)
# ---------------------------------------------------------------------------


class CommandRunner(Protocol):
    """Protocol for running shell commands.  Injected to enable testing."""

    def run(
        self,
        args: list[str],
        *,
        check: bool = False,
        capture_output: bool = False,
        cwd: Path | None = None,
    ) -> subprocess.CompletedProcess[str]: ...

    def sleep(self, seconds: float) -> None: ...


@dataclass
class RealCommandRunner:
    """Thin wrapper around subprocess + time.sleep for production use."""

    def run(
        self,
        args: list[str],
        *,
        check: bool = False,
        capture_output: bool = False,
        cwd: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            args,
            check=check,
            capture_output=capture_output,
            text=True,
            cwd=str(cwd) if cwd else None,
        )

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


# ---------------------------------------------------------------------------
# Supervisor
# ---------------------------------------------------------------------------


@dataclass
class MergeSupervisor:
    """State-machine supervisor for a single PR merge.

    Parameters
    ----------
    pr_number:
        GitHub PR number to merge.
    worktree_path:
        Absolute path to the git worktree for this PR's branch.
        Required when BEHIND handling needs to rebase.
    max_attempts:
        Per-PR attempt budget before escalation.
    runner:
        Command runner (swap out for a fake in tests).
    """

    pr_number: int
    worktree_path: Path | None = None
    max_attempts: int = MAX_ATTEMPTS
    runner: CommandRunner = field(default_factory=RealCommandRunner)

    # Internal state (not constructor params)
    _attempt: int = field(default=0, init=False, repr=False)
    _actions_taken: list[str] = field(default_factory=list, init=False, repr=False)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Execute the supervisor loop until merge succeeds or escalation.

        Raises
        ------
        EscalateError
            When human intervention is required (DIRTY, unexpected state,
            exhausted budget, or unresolvable BLOCKED subcase).
        """
        while self._attempt < self.max_attempts:
            self._attempt += 1
            logger.info(
                "PR #%d supervisor attempt %d/%d",
                self.pr_number,
                self._attempt,
                self.max_attempts,
            )

            state = self._get_merge_state()
            logger.info("PR #%d mergeStateStatus=%s", self.pr_number, state)

            if state in MERGEABLE_STATES:
                self._merge()
                return  # success

            if state == "BEHIND":
                self._handle_behind()
                # continue loop — re-check state after rebase

            elif state == "BLOCKED":
                self._handle_blocked()
                # continue loop — re-check after diagnosis

            elif state == "DIRTY":
                self._escalate(state, "Merge conflict detected; needs human resolution.")

            elif state in RESOLVING_STATES:  # UNKNOWN
                logger.info(
                    "PR #%d state=%s (GitHub recomputing); sleeping %ds",
                    self.pr_number,
                    state,
                    UNKNOWN_SLEEP_SECONDS,
                )
                self.runner.sleep(UNKNOWN_SLEEP_SECONDS)
                # continue loop

            else:
                self._escalate(
                    state,
                    f"Unexpected mergeStateStatus={state!r}; see GitHub PR for details.",
                )

        # Budget exhausted
        state_dump = self._dump_pr_state()
        raise EscalateError(
            self.pr_number,
            "BUDGET_EXHAUSTED",
            f"Exceeded max_attempts={self.max_attempts}; actions taken: {self._actions_taken}",
            state_dump=state_dump,
        )

    # ------------------------------------------------------------------
    # State machine handlers
    # ------------------------------------------------------------------

    def _merge(self) -> None:
        """Execute `gh pr merge --<method> --delete-branch`."""
        method = _merge_method()
        logger.info("PR #%d: state CLEAN/UNSTABLE → merging (--%s)", self.pr_number, method)
        result = self.runner.run(
            [
                "gh",
                "pr",
                "merge",
                str(self.pr_number),
                f"--{method}",
                "--delete-branch",
            ],
            capture_output=True,
        )
        if result.returncode != 0:
            # gh pr merge failed even though mergeStateStatus was CLEAN.
            # Re-query the state and escalate with detail.
            state = self._get_merge_state()
            raise EscalateError(
                self.pr_number,
                state,
                f"gh pr merge failed (exit {result.returncode}): {result.stderr.strip()}",
            )
        self._actions_taken.append("merged")

    def _handle_behind(self) -> None:
        """Rebase the worktree branch on origin/master and force-push."""
        if self.worktree_path is None:
            self._escalate(
                "BEHIND",
                "Cannot auto-rebase: worktree_path not set. "
                "Set worktree_path on MergeSupervisor and retry.",
            )

        logger.info(
            "PR #%d: state BEHIND → rebasing %s on origin/%s",
            self.pr_number,
            self.worktree_path,
            DEFAULT_BRANCH,
        )

        # Guard: do not rebase if operator has staged changes in the worktree.
        status_result = self.runner.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            cwd=self.worktree_path,
        )
        if status_result.stdout.strip():
            self._escalate(
                "BEHIND",
                f"Worktree {self.worktree_path} has uncommitted changes; "
                "refusing to auto-rebase to avoid trampling operator work.",
            )

        # Fetch latest refs
        self.runner.run(
            ["git", "fetch", "origin"],
            check=True,
            cwd=self.worktree_path,
        )

        # Rebase
        rebase_result = self.runner.run(
            ["git", "pull", "--rebase", "origin", DEFAULT_BRANCH],
            capture_output=True,
            cwd=self.worktree_path,
        )
        if rebase_result.returncode != 0:
            self._escalate(
                "BEHIND",
                f"git pull --rebase failed: {rebase_result.stderr.strip()}",
            )

        # Force-push
        push_result = self.runner.run(
            ["git", "push", "--force-with-lease"],
            capture_output=True,
            cwd=self.worktree_path,
        )
        if push_result.returncode != 0:
            self._escalate(
                "BEHIND",
                f"git push --force-with-lease failed: {push_result.stderr.strip()}",
            )

        self._actions_taken.append("rebase+push")
        logger.info(
            "PR #%d: rebase+push done; sleeping %ds before re-check",
            self.pr_number,
            BEHIND_SLEEP_SECONDS,
        )
        self.runner.sleep(BEHIND_SLEEP_SECONDS)

    def _handle_blocked(self) -> None:
        """Diagnose BLOCKED and attempt automatic resolution.

        Subcases (in order of detection):
          (a) Stale FAILURE on same commit SHA → empty-commit workaround.
          (b) Everything else → escalate (required-check rename, branch
              protection change, or an unsatisfied AI review gate).
        """
        logger.info("PR #%d: state BLOCKED → diagnosing", self.pr_number)

        # Fetch check runs for the PR's head commit
        checks_result = self.runner.run(
            [
                "gh",
                "pr",
                "checks",
                str(self.pr_number),
                "--json",
                "name,state,conclusion,startedAt",
            ],
            capture_output=True,
        )

        failed_checks: list[dict[str, str]] = []
        if checks_result.returncode == 0 and checks_result.stdout.strip():
            try:
                checks = json.loads(checks_result.stdout)
                failed_checks = [
                    c for c in checks if c.get("conclusion") in ("FAILURE", "failure")
                ]
            except json.JSONDecodeError:
                pass

        # Subcase (a): stale FAILURE — checks failed but HEAD hasn't changed;
        # the FAILURE may have been from an earlier SHA.  Push an empty commit
        # to re-trigger CI.
        if failed_checks and self.worktree_path is not None:
            head_sha = self._get_head_sha()
            stale = self._is_stale_failure(failed_checks, head_sha)
            if stale:
                logger.info(
                    "PR #%d: stale FAILURE detected on SHA %s → empty-commit workaround",
                    self.pr_number,
                    head_sha,
                )
                self._push_empty_commit()
                self._actions_taken.append("empty-commit")
                return

        # Subcase (b): anything else is beyond auto-resolution.
        self._escalate(
            "BLOCKED",
            "BLOCKED state could not be auto-resolved (not a stale FAILURE). "
            "Possible causes: required-check rename mid-wave, an unsatisfied AI "
            "review / branch-protection gate, manual dismissal needed, or a "
            "branch protection rule change. Check the PR on GitHub.",
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_merge_state(self) -> str:
        """Return the current mergeStateStatus string for the PR."""
        result = self.runner.run(
            [
                "gh",
                "pr",
                "view",
                str(self.pr_number),
                "--json",
                "mergeStateStatus",
                "--jq",
                ".mergeStateStatus",
            ],
            capture_output=True,
        )
        if result.returncode != 0:
            logger.warning(
                "PR #%d: gh pr view failed (exit %d): %s",
                self.pr_number,
                result.returncode,
                result.stderr.strip(),
            )
            return "UNKNOWN"
        return result.stdout.strip()

    def _dump_pr_state(self) -> str:
        """Return full PR JSON state for escalation messages."""
        result = self.runner.run(
            [
                "gh",
                "pr",
                "view",
                str(self.pr_number),
                "--json",
                "number,title,mergeStateStatus,mergeable,state,reviewDecision",
            ],
            capture_output=True,
        )
        return result.stdout.strip() if result.returncode == 0 else ""

    def _get_head_sha(self) -> str:
        """Return the current HEAD SHA of the worktree branch."""
        result = self.runner.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            cwd=self.worktree_path,
        )
        return result.stdout.strip() if result.returncode == 0 else ""

    def _is_stale_failure(
        self,
        failed_checks: list[dict[str, str]],
        head_sha: str,
    ) -> bool:
        """Return True when the failed checks appear stale relative to head_sha.

        We consider a failure "stale" when the check's ``startedAt`` timestamp
        is older than the HEAD commit's author date.  When we cannot determine
        the commit date we fall back to True (conservative — triggering a
        re-run is safe).
        """
        if not failed_checks:
            return False
        if not head_sha or self.worktree_path is None:
            # Cannot verify staleness without a worktree or SHA; be conservative
            return True

        # Get commit timestamp for HEAD
        date_result = self.runner.run(
            ["git", "log", "-1", "--format=%ct", head_sha],
            capture_output=True,
            cwd=self.worktree_path,
        )
        if date_result.returncode != 0:
            return True  # conservative

        try:
            head_ts = int(date_result.stdout.strip())
        except ValueError:
            return True  # conservative

        # Parse startedAt from the first failed check (ISO 8601)
        started_at = failed_checks[0].get("startedAt", "")
        if not started_at:
            return True  # conservative — no timestamp means we can't tell

        try:
            import datetime

            check_ts = int(
                datetime.datetime.fromisoformat(started_at.replace("Z", "+00:00")).timestamp()
            )
        except (ValueError, TypeError):
            return True  # conservative

        # The check started BEFORE the HEAD commit → definitely stale
        return check_ts < head_ts

    def _push_empty_commit(self) -> None:
        """Push an empty commit to re-trigger CI on the PR branch."""
        if self.worktree_path is None:
            return
        self.runner.run(
            ["git", "commit", "--allow-empty", "-m", "ci: re-trigger checks [empty]"],
            check=True,
            cwd=self.worktree_path,
        )
        push_result = self.runner.run(
            ["git", "push"],
            capture_output=True,
            cwd=self.worktree_path,
        )
        if push_result.returncode != 0:
            logger.warning(
                "PR #%d: git push after empty commit failed: %s",
                self.pr_number,
                push_result.stderr.strip(),
            )

    def _escalate(self, state: str, reason: str) -> None:
        """Raise EscalateError with current PR state dump."""
        state_dump = self._dump_pr_state()
        raise EscalateError(
            self.pr_number,
            state,
            reason,
            state_dump=state_dump,
        )


# ---------------------------------------------------------------------------
# Pre-emptive rebase helper (post-merge cascade for N>1 PRs)
# ---------------------------------------------------------------------------


def preemptive_rebase(
    worktree_paths: list[Path],
    runner: CommandRunner | None = None,
) -> dict[Path, str]:
    """After merging PR-A, immediately rebase all remaining worktrees.

    This is the recommended pattern when merging multiple PRs sequentially.
    Rather than waiting for each trailing PR to go BEHIND (and then spinning
    through the supervisor loop), rebase them all proactively right after the
    first merge completes — before CI even starts on master.

    Parameters
    ----------
    worktree_paths:
        Ordered list of worktrees to rebase (the trailing PRs in the merge queue).
    runner:
        Optional CommandRunner (defaults to RealCommandRunner).

    Returns
    -------
    dict[Path, str]
        Mapping of worktree path → outcome string ("ok", "dirty", "error:<msg>").
    """
    if runner is None:
        runner = RealCommandRunner()

    results: dict[Path, str] = {}

    for wt in worktree_paths:
        logger.info("Pre-emptive rebase: %s", wt)

        # Guard: uncommitted changes
        status_result = runner.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            cwd=wt,
        )
        if status_result.stdout.strip():
            logger.warning("Pre-emptive rebase skipped for %s: dirty worktree", wt)
            results[wt] = "dirty"
            continue

        # Fetch + rebase
        runner.run(["git", "fetch", "origin"], cwd=wt)
        rebase_result = runner.run(
            ["git", "pull", "--rebase", "origin", DEFAULT_BRANCH],
            capture_output=True,
            cwd=wt,
        )
        if rebase_result.returncode != 0:
            msg = rebase_result.stderr.strip()
            logger.error("Pre-emptive rebase FAILED for %s: %s", wt, msg)
            results[wt] = f"error:{msg}"
            continue

        push_result = runner.run(
            ["git", "push", "--force-with-lease"],
            capture_output=True,
            cwd=wt,
        )
        if push_result.returncode != 0:
            msg = push_result.stderr.strip()
            logger.error("Pre-emptive push FAILED for %s: %s", wt, msg)
            results[wt] = f"error:{msg}"
            continue

        results[wt] = "ok"
        logger.info("Pre-emptive rebase done: %s", wt)

    return results


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sprint merge supervisor: handles BEHIND/BLOCKED/DIRTY/UNKNOWN PR states.",
    )
    parser.add_argument("--pr", type=int, required=True, help="PR number to merge.")
    parser.add_argument(
        "--worktree",
        type=Path,
        default=None,
        help=(
            "Path to the git worktree for this PR's branch (required for BEHIND "
            "handling). Recommended in-clone layout: .worktrees/<ticket>."
        ),
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=MAX_ATTEMPTS,
        help=f"Per-PR attempt budget (default: {MAX_ATTEMPTS}).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stderr,
    )
    args = _build_parser().parse_args(argv)

    supervisor = MergeSupervisor(
        pr_number=args.pr,
        worktree_path=args.worktree,
        max_attempts=args.max_attempts,
    )
    try:
        supervisor.run()
        print(f"PR #{args.pr}: merged successfully.")
        return 0
    except EscalateError as exc:
        print(f"ESCALATE: {exc}", file=sys.stderr)
        if exc.state_dump:
            print(f"PR state dump:\n{exc.state_dump}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
