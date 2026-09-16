"""Offline HTML view of a stripped estate (no CDN, no answer-key labels)."""

from __future__ import annotations

from typing import Any

_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>cloudforge lab estate</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 1.5rem; }}
    table {{ border-collapse: collapse; margin: 1rem 0; }}
    th, td {{ border: 1px solid #ccc; padding: 0.3rem 0.6rem; text-align: left; }}
    pre {{ background: #f6f6f6; padding: 0.8rem; overflow: auto; }}
  </style>
</head>
<body>
  <h1>Estate</h1>
  <p>Investigate the resources and relationships. This page does not include an answer key.</p>
  <h2>Resources</h2>
  <table>
    <tr><th>id</th><th>type</th><th>name</th></tr>
    {rows}
  </table>
  <h2>Relationships</h2>
  <pre>{edges}</pre>
</body>
</html>
"""


def render_estate_html(estate: dict[str, Any]) -> str:
    """Self-contained HTML tables for a stripped estate dict."""
    rows = "\n    ".join(
        f"<tr><td><code>{_esc(n['id'])}</code></td>"
        f"<td>{_esc(n['type'])}</td><td>{_esc(n['name'])}</td></tr>"
        for n in estate["nodes"]
    )
    edge_lines = "\n".join(f"{e['from']} --{e['type']}--> {e['to']}" for e in estate["edges"])
    return _PAGE.format(rows=rows, edges=_esc(edge_lines))


def _esc(value: object) -> str:
    text = str(value)
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
