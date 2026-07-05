"""Linear tracker backend (best-effort mirror).

Linear has no first-class numeric "estimate minutes" or "model" field, so this
adapter mirrors the canonical CSV state onto the Linear issue as labels
(`ai-est:<n>m`, `model:<family>`) and maps `status` onto the issue's workflow
state. It is intentionally fail-soft: any error (missing CLI/MCP, auth, network)
is swallowed so a planning op never blocks on the tracker.

Wiring: this template ships the seam, not the credentials. A concrete project
fills in `_linear_call` with its Linear access path -- typically the Linear MCP
tools available to the agent, or a thin `linear-cli`/GraphQL wrapper. Until then
the adapter degrades to a no-op (CSV remains the source of truth).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any

# Map canonical statuses -> Linear workflow state names (override per project).
STATUS_MAP = {
    "planned": "Backlog",
    "ready": "Todo",
    "in_progress": "In Progress",
    "in_review": "In Review",
    "done": "Done",
}


def _linear_call(args: list[str]) -> None:
    """Invoke a `linear` CLI if one is on PATH; otherwise no-op.

    Projects that drive Linear through the MCP server instead should replace
    this body with their MCP call. Kept tiny and dependency-free on purpose.
    """
    cli = os.environ.get("LINEAR_CLI", "linear")
    if not shutil.which(cli):
        return
    subprocess.run([cli, *args], check=False, capture_output=True, timeout=10)


def mirror(ticket: str, fields: dict[str, Any]) -> None:
    try:
        if fields.get("estimate_minutes") not in (None, ""):
            _linear_call(["label", ticket, f"ai-est:{fields['estimate_minutes']}m"])
        if fields.get("recommended_model"):
            _linear_call(["label", ticket, f"model:{fields['recommended_model']}"])
        if fields.get("status"):
            state = STATUS_MAP.get(fields["status"], fields["status"])
            _linear_call(["state", ticket, state])
    except Exception:
        return None


def lead_time(ticket: str) -> dict[str, Any] | None:
    # Requires reading Linear issue history; left to the concrete project.
    return None
