"""In-memory SimWorld implementation."""

from __future__ import annotations

from collections.abc import Iterable

from lemmings.schemas import (
    PR,
    LedgerRow,
    ReviewResult,
    Ticket,
    TicketStatus,
)


class SimWorld:
    """Pure in-memory pipeline state."""

    def __init__(self, sprint_budget_usd: float = 50.0) -> None:
        self._tickets: dict[str, Ticket] = {}
        self._prs: dict[str, PR] = {}
        self._reviews: dict[str, list[ReviewResult]] = {}
        self._ledger: list[LedgerRow] = []
        self._sprint_budget_usd: float = sprint_budget_usd
        self._budget_locked: bool = False
        self._budget_lock_reason: str | None = None

    # --- Tickets ---
    def add_ticket(self, ticket: Ticket) -> None:
        if ticket.id in self._tickets:
            raise ValueError(f"ticket {ticket.id} already exists")
        self._tickets[ticket.id] = ticket

    def get_ticket(self, ticket_id: str) -> Ticket:
        return self._tickets[ticket_id]

    def update_ticket_status(self, ticket_id: str, status: TicketStatus) -> None:
        self._tickets[ticket_id].status = status

    def list_tickets(self, status: TicketStatus | None = None) -> list[Ticket]:
        if status is None:
            return list(self._tickets.values())
        return [t for t in self._tickets.values() if t.status == status]

    # --- PRs ---
    def open_pr(self, pr: PR) -> None:
        self._prs[pr.ticket_id] = pr

    def get_pr(self, ticket_id: str) -> PR | None:
        return self._prs.get(ticket_id)

    def list_open_prs(self) -> list[PR]:
        merged = {
            t.id for t in self._tickets.values() if t.status == TicketStatus.MERGED
        }
        return [pr for tid, pr in self._prs.items() if tid not in merged]

    def close_pr(self, ticket_id: str, merged: bool) -> None:
        if ticket_id not in self._prs:
            raise KeyError(f"no PR for ticket {ticket_id}")
        if merged:
            self.update_ticket_status(ticket_id, TicketStatus.MERGED)

    # --- Reviews ---
    def record_review(self, result: ReviewResult) -> None:
        self._reviews.setdefault(result.ticket_id, []).append(result)

    def list_reviews(self, ticket_id: str) -> list[ReviewResult]:
        return list(self._reviews.get(ticket_id, ()))

    # --- Ledger ---
    def append_ledger(self, row: LedgerRow) -> None:
        self._ledger.append(row)

    def ledger_rows(self) -> Iterable[LedgerRow]:
        return tuple(self._ledger)

    def total_billed_usd(self) -> float:
        return sum(r.compute_cost_usd for r in self._ledger)

    # --- Sprint metadata ---
    def sprint_budget_usd(self) -> float:
        return self._sprint_budget_usd

    def set_sprint_budget_usd(self, value: float) -> None:
        self._sprint_budget_usd = value

    def is_budget_locked(self) -> bool:
        return self._budget_locked

    def lock_budget(self, reason: str) -> None:
        self._budget_locked = True
        self._budget_lock_reason = reason

    def budget_lock_reason(self) -> str | None:
        return self._budget_lock_reason
