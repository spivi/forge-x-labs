"""GitHub Projects (v2) tracker backend (best-effort mirror).

Mirrors canonical CSV state onto a GitHub issue: estimate + model + status as
labels (and, where a project field exists, the native Estimate field). Uses the
`gh` CLI if present; fail-soft otherwise so planning never blocks on the tracker.

`ticket` is assumed to be a GitHub issue number (or resolvable to one by the
project). Repos with a Projects v2 board can extend `lead_time` to read the
status-change timeline; the template ships the seam, not the board wiring.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import Any


def _gh(args: list[str]) -> None:
    if not shutil.which("gh"):
        return
    subprocess.run(["gh", *args], check=False, capture_output=True, timeout=15)


def _issue_number(ticket: str) -> str | None:
    # Accept a bare number or a PREFIX-123 form (take the trailing digits).
    digits = "".join(ch for ch in ticket if ch.isdigit())
    return digits or None


def mirror(ticket: str, fields: dict[str, Any]) -> None:
    try:
        num = _issue_number(ticket)
        if not num:
            return
        labels: list[str] = []
        if fields.get("estimate_minutes") not in (None, ""):
            labels.append(f"ai-est:{fields['estimate_minutes']}m")
        if fields.get("recommended_model"):
            labels.append(f"model:{fields['recommended_model']}")
        for label in labels:
            _gh(["issue", "edit", num, "--add-label", label])
    except Exception:
        return None


def lead_time(ticket: str) -> dict[str, Any] | None:
    # Requires the Projects v2 status timeline; left to the concrete project.
    return None
