"""The `none` tracker backend: CSV is the only store, nothing is mirrored.

This is the default. The full learning loop (estimate, gate, debrief, refresh)
works with this backend alone -- no Linear, no GitHub Projects required.
"""

from __future__ import annotations

from typing import Any


def mirror(ticket: str, fields: dict[str, Any]) -> None:
    """No external tracker -- the CSV write in tracker.py is the whole story."""
    return None


def lead_time(ticket: str) -> dict[str, Any] | None:
    """No external board to read status transitions from."""
    return None
