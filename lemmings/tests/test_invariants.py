"""Unit tests for invariants — synthetic traces, no full sim."""

from __future__ import annotations

import pytest

from lemmings.invariants.budget import no_agents_after_budget_exceeded
from lemmings.invariants.escalation import escalation_when_loop_exhausted
from lemmings.invariants.ledger import ledger_monotonic
from lemmings.invariants.merge import merge_order_respects_conflicts
from lemmings.invariants.retry import retries_capped
from lemmings.schemas import LedgerRow, TraceEvent


def _ev(clock: float, kind: str, **payload: object) -> TraceEvent:
    return TraceEvent(clock=clock, kind=kind, payload=dict(payload))


def test_budget_invariant_passes_when_no_spawns_after() -> None:
    no_agents_after_budget_exceeded(
        [_ev(10.0, "DEVELOPER_STARTED"), _ev(20.0, "BUDGET_EXCEEDED")]
    )


def test_budget_invariant_fails_when_spawn_after() -> None:
    with pytest.raises(AssertionError, match="agent spawned"):
        no_agents_after_budget_exceeded(
            [
                _ev(10.0, "DEVELOPER_STARTED"),
                _ev(20.0, "BUDGET_EXCEEDED"),
                _ev(25.0, "DEVELOPER_STARTED"),
            ]
        )


def test_retries_capped_passes_at_cap() -> None:
    retries_capped(
        [_ev(t * 1.0, "REVIEW_COMPLETED", ticket_id="T-1") for t in range(3)],
        max_attempts=3,
    )


def test_retries_capped_fails_over_cap() -> None:
    with pytest.raises(AssertionError, match="reviewed 4 times"):
        retries_capped(
            [_ev(t * 1.0, "REVIEW_COMPLETED", ticket_id="T-1") for t in range(4)],
            max_attempts=3,
        )


def test_escalation_passes_when_escalated() -> None:
    events = [
        _ev(1.0, "REVIEW_COMPLETED", ticket_id="T-1", verdict="fail"),
        _ev(2.0, "REVIEW_COMPLETED", ticket_id="T-1", verdict="fail"),
        _ev(3.0, "REVIEW_COMPLETED", ticket_id="T-1", verdict="fail"),
        _ev(4.0, "ESCALATED", ticket_id="T-1"),
    ]
    escalation_when_loop_exhausted(events, max_attempts=3)


def test_escalation_fails_when_missed() -> None:
    events = [
        _ev(1.0, "REVIEW_COMPLETED", ticket_id="T-1", verdict="fail"),
        _ev(2.0, "REVIEW_COMPLETED", ticket_id="T-1", verdict="fail"),
        _ev(3.0, "REVIEW_COMPLETED", ticket_id="T-1", verdict="fail"),
    ]
    with pytest.raises(AssertionError, match="not escalated"):
        escalation_when_loop_exhausted(events, max_attempts=3)


def test_merge_invariant_passes_for_disjoint_files() -> None:
    events = [
        _ev(10.0, "MERGE_PLAN", order=["A", "B"], conflicts=[]),
        _ev(10.0, "MERGED", ticket_id="A"),
        _ev(10.0, "MERGED", ticket_id="B"),
    ]
    merge_order_respects_conflicts(events)


def test_merge_invariant_fails_for_concurrent_conflicting_merges() -> None:
    events = [
        _ev(10.0, "MERGE_PLAN", order=["A"], conflicts=[["A", "B"]]),
        _ev(10.0, "MERGED", ticket_id="A"),
        _ev(10.0, "MERGED", ticket_id="B"),
    ]
    with pytest.raises(AssertionError, match="conflicting tickets"):
        merge_order_respects_conflicts(events)


def test_ledger_monotonic_passes() -> None:
    rows = [
        LedgerRow(
            timestamp="2026-01-01T00:00:00Z",
            agent="developer",
            session_id="s",
            provider="sim",
            model="m",
            input_tokens=0,
            output_tokens=0,
            cache_creation_tokens=0,
            cache_read_tokens=0,
            compute_cost_usd=v,
            billing_type="sim",
            billed_usd=v,
            ticket="T",
        )
        for v in (1.0, 2.0, 0.5)
    ]
    ledger_monotonic(rows)


def test_ledger_monotonic_fails_on_negative() -> None:
    bad_row = LedgerRow(
        timestamp="2026-01-01T00:00:00Z",
        agent="developer",
        session_id="s",
        provider="sim",
        model="m",
        input_tokens=0,
        output_tokens=0,
        cache_creation_tokens=0,
        cache_read_tokens=0,
        compute_cost_usd=-1.0,
        billing_type="sim",
        billed_usd=-1.0,
        ticket="T",
    )
    with pytest.raises(AssertionError, match="negative"):
        ledger_monotonic([bad_row])
