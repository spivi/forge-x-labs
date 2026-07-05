"""Unit tests for the decision core."""

from __future__ import annotations

from lemmings.core.budget_gate import evaluate_budget
from lemmings.core.escalation import evaluate_escalation
from lemmings.core.merge_order import plan_merges
from lemmings.core.retry_loop import evaluate_retry
from lemmings.core.select_ticket import select_next_ticket
from lemmings.schemas import (
    PR,
    LedgerRow,
    ReviewResult,
    ReviewVerdict,
    Ticket,
    TicketStatus,
)
from lemmings.world.sim import SimWorld


def _ledger_row(amount: float) -> LedgerRow:
    return LedgerRow(
        timestamp="2026-01-01T00:00:00Z",
        agent="developer",
        session_id="s",
        provider="sim",
        model="m",
        input_tokens=0,
        output_tokens=0,
        cache_creation_tokens=0,
        cache_read_tokens=0,
        compute_cost_usd=amount,
        billing_type="sim",
        billed_usd=amount,
        ticket="T",
    )


# ---- budget_gate ----


def test_budget_allows_under_cap() -> None:
    w = SimWorld(sprint_budget_usd=10.0)
    w.append_ledger(_ledger_row(5.0))
    decision = evaluate_budget(w, hard_cap_factor=1.2)
    assert decision.allow
    assert decision.reason == "ok"


def test_budget_blocks_over_hard_cap() -> None:
    w = SimWorld(sprint_budget_usd=10.0)
    w.append_ledger(_ledger_row(15.0))  # over 12 hard cap
    decision = evaluate_budget(w, hard_cap_factor=1.2)
    assert not decision.allow
    assert decision.reason == "hard_cap_exceeded"


def test_budget_locked_blocks() -> None:
    w = SimWorld(sprint_budget_usd=10.0)
    w.lock_budget(reason="manual")
    decision = evaluate_budget(w)
    assert not decision.allow
    assert decision.reason == "budget_locked"


# ---- retry_loop ----


def _world_with_reviews(verdicts: list[ReviewVerdict]) -> SimWorld:
    w = SimWorld()
    w.add_ticket(Ticket(id="T-1", title="x"))
    for v in verdicts:
        w.record_review(
            ReviewResult(
                ticket_id="T-1",
                verdict=v,
                violations=10 if v is ReviewVerdict.FAIL else 0,
                duration_min=2.0,
            )
        )
    return w


def test_retry_pass_means_merge() -> None:
    w = _world_with_reviews([ReviewVerdict.FAIL, ReviewVerdict.PASS])
    decision = evaluate_retry(w, "T-1", max_attempts=3)
    assert decision.action == "merge"


def test_retry_fail_under_cap_means_rework() -> None:
    w = _world_with_reviews([ReviewVerdict.FAIL])
    decision = evaluate_retry(w, "T-1", max_attempts=3)
    assert decision.action == "rework"


def test_retry_fail_at_cap_means_escalate() -> None:
    w = _world_with_reviews([ReviewVerdict.FAIL] * 3)
    decision = evaluate_retry(w, "T-1", max_attempts=3)
    assert decision.action == "escalate"


# ---- escalation ----


def test_escalation_only_when_loop_exhausted() -> None:
    w = _world_with_reviews([ReviewVerdict.FAIL])
    assert not evaluate_escalation(w, "T-1", max_attempts=3).should_escalate
    w = _world_with_reviews([ReviewVerdict.FAIL] * 3)
    assert evaluate_escalation(w, "T-1", max_attempts=3).should_escalate


# ---- select_ticket ----


def test_select_next_ticket_fifo_by_id() -> None:
    w = SimWorld()
    w.add_ticket(Ticket(id="T-2", title="b"))
    w.add_ticket(Ticket(id="T-1", title="a"))
    w.add_ticket(Ticket(id="T-0", title="z", status=TicketStatus.MERGED))
    selected = select_next_ticket(w)
    assert selected is not None and selected.id == "T-1"


def test_select_returns_none_when_empty() -> None:
    w = SimWorld()
    assert select_next_ticket(w) is None


# ---- merge_order ----


def _pr(ticket: str, files: tuple[str, ...], opened: float) -> PR:
    return PR(
        ticket_id=ticket,
        branch=f"feat/{ticket}",
        files_touched=files,
        lines_added=10,
        bugs_introduced=0,
        opened_at=opened,
    )


def test_merge_no_conflicts_keeps_all() -> None:
    plan = plan_merges([
        _pr("A", ("x.py",), 10),
        _pr("B", ("y.py",), 20),
    ])
    assert plan.order == ("A", "B")
    assert plan.conflict_pairs == ()


def test_merge_overlap_serialises() -> None:
    plan = plan_merges([
        _pr("A", ("auth.py",), 10),
        _pr("B", ("auth.py",), 20),
    ])
    assert plan.order == ("A",)
    assert plan.conflict_pairs == (("A", "B"),)


def test_merge_three_way_conflict() -> None:
    plan = plan_merges([
        _pr("A", ("auth.py",), 10),
        _pr("B", ("auth.py", "session.py"), 20),
        _pr("C", ("session.py",), 30),
    ])
    # A clears first (no conflicts yet); B overlaps A on auth.py → blocked;
    # C only conflicts with B (not yet cleared) so C clears too.
    assert plan.order == ("A", "C")
    assert ("A", "B") in plan.conflict_pairs
