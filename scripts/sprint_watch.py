"""Sprint watch supervisor: reactive reviewer dispatch as each agent opens a PR.

Extends the sprint execute flow with a resident watch loop that fires a fresh-context
reviewer the moment a developer agent opens its PR, without waiting for sibling agents.

Architecture:
  - ``WatchSupervisor.run()`` polls for new open PRs at ``poll_interval`` seconds.
  - When a new PR is detected for a wave ticket, ``_dispatch_reviewer()`` is called
    synchronously (blocks until reviewer + fix cycles complete, then queues for merge).
  - ``_merge_clean_prs()`` delegates to ``MergeSupervisor`` for each clean PR.
  - Pre-emptive rebase of remaining worktrees runs after each merge (BEHIND prevention).
  - State is durably written to a JSON file so a crashed session can resume.

Usage (from /sprint watch action or --watch flag in SKILL.md):

  from pathlib import Path
  from scripts.sprint_watch import WatchSupervisor

  sup = WatchSupervisor(
      wave_tickets=[101, 102, 103],          # GitHub issue numbers in this wave
      worktree_root=Path(".worktrees"),       # parent dir of per-ticket worktrees
      state_path=Path(".dev-context/sprint-watch-state.json"),
  )
  sup.run(total_agents=3)

CLI:

  python scripts/sprint_watch.py --tickets 101 102 103 --worktree-root .worktrees

``worktree_root`` is the parent directory of per-ticket worktrees and defaults to
``.worktrees`` (the in-clone layout). Per-ticket worktrees are resolved by globbing
``<worktree_root>/<ticket>-*`` (or the exact ``<worktree_root>/<ticket>`` dir).
Projects using the sibling worktree layout (``../<project>--<ticket>``) pass
``--worktree-root ..`` and may need to adjust the glob in
``_worktree_for_ticket`` to match their naming pattern.

Max review cycles per PR: 3 (after 3 a P1 escalates). Poll interval default: 60s.

Session-drop resilience:
  On restart, pass the same ``state_path`` and ``wave_tickets``.  The supervisor picks
  up from the last durable checkpoint: already-merged PRs are skipped, in-flight
  reviewers are restarted from cycle 1 (conservative but safe), and clean PRs are
  immediately queued for merge.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol

# Allow `import sprint_merge_supervisor` to resolve whether this module is run as
# a CLI (`python scripts/sprint_watch.py`) or loaded via importlib in tests —
# same seam as scripts/debrief.py importing its sibling `dataset`.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from sprint_merge_supervisor import (  # noqa: E402  (sys.path mutated just above)
    MergeSupervisor,
    preemptive_rebase,
)

logger = logging.getLogger(__name__)

MAX_REVIEW_CYCLES: int = 3
DEFAULT_POLL_INTERVAL: int = 60  # seconds


# ---------------------------------------------------------------------------
# State dataclasses
# ---------------------------------------------------------------------------


@dataclass
class PRState:
    """Per-PR review state tracked across the watch loop."""

    ticket: int
    pr: int
    status: str = "pending"  # pending | in_flight | clean | merged | escalated
    cycle: int = 0


@dataclass
class WatchState:
    """Full wave state persisted to the state file."""

    wave_tickets: list[int] = field(default_factory=list)
    pr_states: dict[int, PRState] = field(default_factory=dict)

    def wave_complete(self, total_agents: int) -> bool:
        """True when every agent has a merged PR (no pending, no in-flight)."""
        merged = sum(1 for s in self.pr_states.values() if s.status == "merged")
        return merged >= total_agents


# ---------------------------------------------------------------------------
# State-file I/O
# ---------------------------------------------------------------------------


def save_watch_state(path: Path, state: WatchState) -> None:
    """Persist ``state`` to ``path`` as JSON using an atomic rename.

    Writes to a sibling ``.tmp`` file first, then ``os.replace``-es it into
    place so a concurrent read never sees a partially-written file.
    """
    import contextlib
    import os
    import tempfile

    path.parent.mkdir(parents=True, exist_ok=True)
    raw = {
        "wave_tickets": state.wave_tickets,
        "pr_states": {str(pr): asdict(ps) for pr, ps in state.pr_states.items()},
    }
    payload = json.dumps(raw, indent=2)
    # Write to a temp file in the same directory so os.replace is atomic
    # (same filesystem — no cross-device rename).
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(payload)
        os.replace(tmp_path, path)
    except Exception:
        # Best-effort cleanup on failure; re-raise so the caller knows.
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise


def load_watch_state(path: Path, wave_tickets: list[int]) -> WatchState:
    """Load state from ``path``, or return a fresh state if the file is absent."""
    if not path.exists():
        return WatchState(wave_tickets=list(wave_tickets))
    try:
        raw = json.loads(path.read_text())
        pr_states = {int(pr): PRState(**ps) for pr, ps in raw.get("pr_states", {}).items()}
        return WatchState(
            wave_tickets=raw.get("wave_tickets", list(wave_tickets)),
            pr_states=pr_states,
        )
    except (json.JSONDecodeError, TypeError, KeyError):
        logger.warning("sprint-watch: corrupt state file %s — starting fresh", path)
        return WatchState(wave_tickets=list(wave_tickets))


# ---------------------------------------------------------------------------
# CommandRunner protocol (injected for testing)
# ---------------------------------------------------------------------------


class CommandRunner(Protocol):
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
# Watch supervisor
# ---------------------------------------------------------------------------


@dataclass
class WatchSupervisor:
    """Resident supervisor that dispatches reviewers as each agent opens a PR.

    Parameters
    ----------
    wave_tickets:
        GitHub issue numbers for all tickets in this wave.
    worktree_root:
        Parent directory of per-ticket worktrees (e.g. ``.worktrees``).
    state_path:
        Where to persist the durable watch state file.
    runner:
        Command runner (swap for a fake in tests).
    poll_interval:
        Seconds between PR-open polls. Set to 0 in tests.
    max_review_cycles:
        Maximum reviewer cycles per PR before escalation (default: 3).
    """

    wave_tickets: list[int]
    worktree_root: Path
    state_path: Path
    runner: CommandRunner = field(default_factory=RealCommandRunner)
    poll_interval: int = DEFAULT_POLL_INTERVAL
    max_review_cycles: int = MAX_REVIEW_CYCLES

    def run(self, total_agents: int) -> None:
        """Resident loop: poll for PRs, review, merge, until wave complete."""
        state = load_watch_state(self.state_path, self.wave_tickets)

        # Fast path: already complete (e.g. resumed after all merges done).
        if state.wave_complete(total_agents):
            logger.info("sprint-watch: wave already complete — nothing to do")
            return

        # Reset any in-flight PRs from a previous crashed session to cycle 1.
        self._reset_in_flight(state)
        save_watch_state(self.state_path, state)

        while not state.wave_complete(total_agents):
            new_prs = self._detect_new_prs(state)
            for pr in new_prs:
                ticket = self._get_pr_ticket(pr)
                if ticket is None:
                    logger.debug("sprint-watch: PR #%d not in wave — skipping", pr)
                    continue
                logger.info(
                    "sprint-watch: PR #%d (ticket #%d) detected — dispatching reviewer",
                    pr,
                    ticket,
                )
                state.pr_states[pr] = PRState(ticket=ticket, pr=pr, status="in_flight", cycle=1)
                save_watch_state(self.state_path, state)
                self._dispatch_reviewer(pr=pr, ticket=ticket, cycle=1, state=state)
                save_watch_state(self.state_path, state)

            self._merge_clean_prs(state)
            save_watch_state(self.state_path, state)

            if state.wave_complete(total_agents):
                break

            if self.poll_interval:
                logger.debug("sprint-watch: sleeping %ds before next poll", self.poll_interval)
                self.runner.sleep(self.poll_interval)

        logger.info("sprint-watch: wave complete — all PRs merged")
        # Leave the state file in place (audit trail); caller may delete it.

    # ------------------------------------------------------------------
    # PR detection
    # ------------------------------------------------------------------

    def list_open_prs(self) -> list[int]:
        """Return a list of open PR numbers in the repository."""
        result = self.runner.run(
            ["gh", "pr", "list", "--state", "open", "--json", "number"],
            capture_output=True,
        )
        if result.returncode != 0:
            logger.warning("sprint-watch: gh pr list failed: %s", result.stderr.strip())
            return []
        try:
            return [item["number"] for item in json.loads(result.stdout)]
        except (json.JSONDecodeError, KeyError):
            return []

    def _detect_new_prs(self, state: WatchState) -> list[int]:
        """Return PR numbers that are open but not yet tracked in ``state``."""
        open_prs = self.list_open_prs()
        return [pr for pr in open_prs if pr not in state.pr_states]

    def _get_pr_ticket(self, pr_number: int) -> int | None:
        """Return the wave-ticket number referenced in PR ``pr_number``'s body.

        Looks for ``#NNN`` or ``Closes #NNN`` patterns and returns the first
        issue number that is in ``self.wave_tickets``, or None if not found.
        """
        result = self.runner.run(
            ["gh", "pr", "view", str(pr_number), "--json", "body"],
            capture_output=True,
        )
        if result.returncode != 0:
            return None
        try:
            body = json.loads(result.stdout).get("body", "")
        except json.JSONDecodeError:
            return None

        for match in re.finditer(r"#(\d+)", body):
            issue = int(match.group(1))
            if issue in self.wave_tickets:
                return issue
        return None

    # ------------------------------------------------------------------
    # Review dispatch
    # ------------------------------------------------------------------

    def _dispatch_reviewer(
        self,
        pr: int,
        ticket: int,
        cycle: int,
        state: WatchState,
    ) -> None:
        """Run the review gate loop (≤ max_review_cycles) for a single PR.

        On PASS  → marks state as ``clean``.
        On P2/P3 → dispatches fix subagent, re-reviews (cycle+1).
        On P1 after max cycles → marks state as ``escalated``.
        """
        for c in range(cycle, self.max_review_cycles + 1):
            verdict = self._spawn_reviewer_task(pr=pr, ticket=ticket, cycle=c)
            counts = verdict.get("counts", {})
            p1 = counts.get("p1", 0)
            p2 = counts.get("p2", 0)

            self._record_and_audit(pr=pr, ticket=ticket, verdict=verdict)

            if verdict.get("verdict") == "PASS":
                state.pr_states[pr] = PRState(ticket=ticket, pr=pr, status="clean", cycle=c)
                logger.info("sprint-watch: PR #%d cycle %d → PASS (clean)", pr, c)
                return

            if p1 and c >= self.max_review_cycles:
                state.pr_states[pr] = PRState(ticket=ticket, pr=pr, status="escalated", cycle=c)
                logger.error(
                    "sprint-watch: PR #%d has P1 after %d cycles — escalated (human needed)",
                    pr,
                    c,
                )
                return

            # P2 or P3 with cycles remaining: dispatch fix subagent and loop.
            if p2 or (p1 and c < self.max_review_cycles):
                logger.info(
                    "sprint-watch: PR #%d cycle %d → FAIL (p1=%d p2=%d) — fix subagent",
                    pr,
                    c,
                    p1,
                    p2,
                )
                self._spawn_fix_task(pr=pr, ticket=ticket, verdict=verdict)

            state.pr_states[pr] = PRState(ticket=ticket, pr=pr, status="in_flight", cycle=c + 1)

        # Should not be reached under normal flow.
        state.pr_states[pr] = PRState(
            ticket=ticket, pr=pr, status="escalated", cycle=self.max_review_cycles
        )

    # ------------------------------------------------------------------
    # Merge
    # ------------------------------------------------------------------

    def _merge_clean_prs(self, state: WatchState) -> None:
        """Merge all PRs with status ``clean``, then pre-emptively rebase siblings."""
        clean = [ps for ps in state.pr_states.values() if ps.status == "clean"]
        remaining_worktrees = self._unmerged_worktrees(state)

        for ps in clean:
            wt = self._worktree_for_ticket(ps.ticket)
            logger.info("sprint-watch: merging PR #%d (ticket #%d)", ps.pr, ps.ticket)
            supervisor = MergeSupervisor(
                pr_number=ps.pr,
                worktree_path=wt,
                max_attempts=5,
            )
            supervisor.run()
            ps.status = "merged"
            logger.info("sprint-watch: PR #%d merged", ps.pr)

            # Pre-emptively rebase remaining open worktrees so they don't go BEHIND.
            remaining = [
                self._worktree_for_ticket(t)
                for t in remaining_worktrees
                if self._worktree_for_ticket(t) and t != ps.ticket
            ]
            if remaining:
                preemptive_rebase([wt for wt in remaining if wt is not None])

    def _unmerged_worktrees(self, state: WatchState) -> list[int]:
        """Return ticket IDs whose PRs have not yet been merged."""
        merged_tickets = {ps.ticket for ps in state.pr_states.values() if ps.status == "merged"}
        return [t for t in self.wave_tickets if t not in merged_tickets]

    def _worktree_for_ticket(self, ticket: int) -> Path | None:
        """Resolve the worktree path for a given ticket number (best-effort).

        Default in-clone layout: ``<worktree_root>/<ticket>`` or
        ``<worktree_root>/<ticket>-*``. Projects using the sibling layout pass a
        different ``worktree_root`` (e.g. ``..``) and may adjust this glob to
        match their ``<project>--<ticket>`` naming.
        """
        # Standard layout: .worktrees/<ticket-number> or .worktrees/<ticket>-*
        direct = self.worktree_root / str(ticket)
        if direct.exists():
            return direct
        # Glob for any directory starting with the ticket number followed by a dash.
        candidates = list(self.worktree_root.glob(f"{ticket}-*"))
        return candidates[0] if candidates else None

    # ------------------------------------------------------------------
    # Seams for testing (override in fakes / integration tests)
    # ------------------------------------------------------------------

    def _spawn_reviewer_task(
        self,
        pr: int,
        ticket: int,
        cycle: int,
    ) -> dict[str, Any]:
        """Dispatch an independent Task-agent reviewer and return its JSON verdict.

        In production this spawns a Claude Task subagent running the
        fresh-reviewer prompt and blocks until the reviewer returns its
        structured JSON verdict.

        The reviewer model is selected by diff surface:
          - Opus for security/architecture surfaces
          - Sonnet otherwise
        """
        # Determine reviewer model from diff surface.
        reviewer_model = self._select_reviewer_model(pr)

        logger.info(
            "sprint-watch: spawning %s reviewer for PR #%d (ticket #%d, cycle %d)",
            reviewer_model,
            pr,
            ticket,
            cycle,
        )
        # In real execution the orchestrator uses the Task tool here.
        # This stub is never called directly — it is always patched in tests
        # and called by the orchestrator's Task-spawning harness in production.
        raise NotImplementedError(
            "WatchSupervisor._spawn_reviewer_task must be wired to the Task tool "
            "by the orchestrator. It is not callable from the CLI standalone path."
        )

    def _spawn_fix_task(
        self,
        pr: int,
        ticket: int,
        verdict: dict[str, Any],
    ) -> None:
        """Dispatch a fix subagent to address P2/P3 findings from ``verdict``.

        The subagent is a developer agent with a constrained prompt: fix ONLY the
        findings listed in ``verdict["findings"]``; do not refactor beyond the fix.
        """
        logger.info(
            "sprint-watch: spawning fix subagent for PR #%d (ticket #%d)",
            pr,
            ticket,
        )
        # Wired to Task tool by the orchestrator (same pattern as _spawn_reviewer_task).
        raise NotImplementedError(
            "WatchSupervisor._spawn_fix_task must be wired to the Task tool by the orchestrator."
        )

    def _record_and_audit(
        self,
        pr: int,
        ticket: int,
        verdict: dict[str, Any],
    ) -> None:
        """Record the reviewer verdict and post the GitHub audit comment.

        Delegates to:
          - ``debrief.py record-review`` (writes kpis/reviews.csv row)
          - ``debrief.py post-review-audit`` (posts PR comment + sets ai-code-review status)
        """
        logger.info("sprint-watch: recording review verdict for PR #%d", pr)
        # This is a seam; wired by the orchestrator in production.
        # In tests it is patched to a no-op.

    def _select_reviewer_model(self, pr: int) -> str:
        """Return ``opus`` for security/architecture surfaces, else ``sonnet``."""
        result = self.runner.run(
            ["gh", "pr", "diff", str(pr), "--name-only"],
            capture_output=True,
        )
        if result.returncode != 0:
            return "sonnet"  # fail open
        changed_files = result.stdout
        arch_pattern = re.compile(r"(tiers/router|journal/|DECISIONS\.md|auth|security\.md)")
        return "opus" if arch_pattern.search(changed_files) else "sonnet"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _reset_in_flight(self, state: WatchState) -> None:
        """On resume, re-queue in-flight PRs so they are re-discovered and re-dispatched.

        Removing the entry from ``pr_states`` causes ``_detect_new_prs`` to see
        them as new on the next poll, which dispatches a fresh reviewer from
        cycle 1 — conservative but safe (reviewers see only the diff, not the
        author's reasoning).  Leaving the entry in place with ``status='in_flight'``
        would deadlock: ``_detect_new_prs`` filters to PRs *not already in*
        ``state.pr_states``, and ``_merge_clean_prs`` only merges ``status='clean'``
        PRs — so the PR would never advance.
        """
        in_flight = [pr for pr, ps in state.pr_states.items() if ps.status == "in_flight"]
        for pr in in_flight:
            logger.info(
                "sprint-watch: re-queuing PR #%d for re-dispatch (session resume)",
                pr,
            )
            del state.pr_states[pr]


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Sprint watch supervisor: dispatch reviewers reactively as each developer "
            "agent opens a PR.  Run from the project root after /sprint execute."
        )
    )
    parser.add_argument(
        "--tickets",
        type=int,
        nargs="+",
        required=True,
        help="GitHub issue numbers for all wave tickets (e.g. --tickets 101 102 103).",
    )
    parser.add_argument(
        "--worktree-root",
        type=Path,
        default=Path(".worktrees"),
        help="Parent dir of per-ticket worktrees (default: .worktrees).",
    )
    parser.add_argument(
        "--state-file",
        type=Path,
        default=Path(".dev-context/sprint-watch-state.json"),
        help="Path to the durable state file (default: .dev-context/sprint-watch-state.json).",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=DEFAULT_POLL_INTERVAL,
        help=f"Seconds between PR polls (default: {DEFAULT_POLL_INTERVAL}).",
    )
    parser.add_argument(
        "--total-agents",
        type=int,
        default=None,
        help="Number of developer agents spawned (defaults to len(--tickets)).",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help=(
            "Resume from the existing state file "
            "(same effect as default; explicit flag for clarity)."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stderr,
    )
    args = _build_parser().parse_args(argv)
    total_agents = args.total_agents or len(args.tickets)

    supervisor = WatchSupervisor(
        wave_tickets=args.tickets,
        worktree_root=args.worktree_root,
        state_path=args.state_file,
        poll_interval=args.poll_interval,
    )
    supervisor.run(total_agents=total_agents)
    print(f"Wave complete. {len(args.tickets)} ticket(s) reviewed and merged.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
