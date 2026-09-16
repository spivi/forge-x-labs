"""Offline HTML view of a stripped estate (no CDN, no answer-key labels)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_TEMPLATE_PATH = Path(__file__).parent / "estate_template.html"


def render_estate_html(estate: dict[str, Any]) -> str:
    """Self-contained interactive layered architecture workbench for stripped estate."""
    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    rows = "\n    ".join(
        f"<tr><td><code>{_esc(n['id'])}</code></td>"
        f"<td>{_esc(n['type'])}</td><td>{_esc(n['name'])}</td></tr>"
        for n in estate["nodes"]
    )
    edge_lines = "\n".join(f"{e['from']} --{e['type']}--> {e['to']}" for e in estate["edges"])

    return (
        template.replace("<!-- ESTATE_JSON_PLACEHOLDER -->", json.dumps(estate))
        .replace("<!-- RAW_ROWS_PLACEHOLDER -->", rows)
        .replace("<!-- RAW_EDGES_PLACEHOLDER -->", _esc(edge_lines))
    )


def _esc(value: object) -> str:
    text = str(value)
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
