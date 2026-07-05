"""Tests for SimWorld."""

from __future__ import annotations

import pytest

from lemmings.schemas import (
    PR,
    LedgerRow,
    ReviewResult,
    ReviewVerdict,
    Ticket,
    TicketStatus,
)
from lemmings.world.sim import SimWorld


def _row(amount: float, ticket: str = "T-1") -> LedgerRow:
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
        ticket=ticket,
    )


def test_ticket_lifecycle() -> None:
    w = SimWorld()
    w.add_ticket(Ticket(id="T-1", title="x"))
    assert w.get_ticket("T-1").status is TicketStatus.BACKLOG
    w.update_ticket_status("T-1", TicketStatus.IN_PROGRESS)
    assert w.get_ticket("T-1").status is TicketStatus.IN_PROGRESS
    assert w.list_tickets(status=TicketStatus.IN_PROGRESS) == [w.get_ticket("T-1")]


def test_duplicate_ticket_rejected() -> None:
    w = SimWorld()
    w.add_ticket(Ticket(id="T-1", title="x"))
    with pytest.raises(ValueError):
        w.add_ticket(Ticket(id="T-1", title="y"))


def test_ledger_total() -> None:
    w = SimWorld()
    w.append_ledger(_row(1.5))
    w.append_ledger(_row(2.5))
    assert w.total_billed_usd() == pytest.approx(4.0)


def test_pr_open_close_cycle() -> None:
    w = SimWorld()
    w.add_ticket(Ticket(id="T-1", title="x"))
    pr = PR(
        ticket_id="T-1",
        branch="feat/T-1",
        files_touched=("a.py",),
        lines_added=50,
        bugs_introduced=1,
        opened_at=10.0,
    )
    w.open_pr(pr)
    assert w.get_pr("T-1") is pr
    assert pr in w.list_open_prs()
    w.close_pr("T-1", merged=True)
    assert w.get_ticket("T-1").status is TicketStatus.MERGED
    assert pr not in w.list_open_prs()


def test_record_and_list_reviews() -> None:
    w = SimWorld()
    w.record_review(
        ReviewResult(ticket_id="T-1", verdict=ReviewVerdict.FAIL, violations=10, duration_min=4.0)
    )
    w.record_review(
        ReviewResult(ticket_id="T-1", verdict=ReviewVerdict.PASS, violations=0, duration_min=2.0)
    )
    reviews = w.list_reviews("T-1")
    assert len(reviews) == 2
    assert reviews[-1].verdict is ReviewVerdict.PASS


def test_budget_lock() -> None:
    w = SimWorld(sprint_budget_usd=10.0)
    assert not w.is_budget_locked()
    w.lock_budget(reason="test")
    assert w.is_budget_locked()
    assert w.budget_lock_reason() == "test"
