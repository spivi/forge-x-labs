"""Canonical CSV store for estimates.csv.

Pure read/upsert helpers over the estimates ledger. RFC 4180 quoting via the
stdlib csv module, so commas/quotes in labels round-trip safely. The column set
is fixed by the header already present in the file; upsert only writes known
columns and preserves every other field of an existing row.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

# Canonical column order. Mirrors .dev-context/kpis/estimates.csv header.
# `effort`/`milestone`/`risk`/`area` are the TYPED dimensions promoted out of the
# free-form `labels` string (see .dev-context/planning/taxonomy.yml). `labels` is
# kept for open-ended tags + back-compat. Old 13-col files keep their header until
# `tracker.py migrate` widens them (store._columns reads the live header on write).
COLUMNS = [
    "ticket",
    "estimate_minutes",
    "type",
    "labels",
    "effort",
    "milestone",
    "risk",
    "area",
    "priority",
    "recommended_model",
    "agent",
    "started_at",
    "status",
    "scope_changed",
    "architectural_deviation",
    "clarifying_questions_asked",
    "caused_by",
]


def read_rows(path: str | Path) -> list[dict[str, str]]:
    """Read all data rows as dicts. Missing file -> []."""
    p = Path(path)
    if not p.exists():
        return []
    with p.open(newline="") as f:
        return list(csv.DictReader(f))


def get_row(path: str | Path, ticket: str) -> dict[str, str] | None:
    """Return the row for `ticket`, or None."""
    for row in read_rows(path):
        if row.get("ticket") == ticket:
            return row
    return None


def _columns(path: Path) -> list[str]:
    """Use the file's existing header if present, else the canonical COLUMNS."""
    if path.exists():
        with path.open(newline="") as f:
            header = f.readline().strip()
        if header:
            return header.split(",")
    return list(COLUMNS)


def _write(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row.get(c, "") for c in columns})


def upsert(path: str | Path, ticket: str, **fields: Any) -> dict[str, str]:
    """Update the row for `ticket` (or append a new one). Only the supplied
    fields are written; all other fields of an existing row are preserved.
    Returns the resulting row."""
    p = Path(path)
    columns = _columns(p)
    rows = read_rows(p)
    updates = {k: ("" if v is None else str(v)) for k, v in fields.items()}

    for row in rows:
        if row.get("ticket") == ticket:
            row.update(updates)
            _write(p, columns, rows)
            return row

    new_row = {c: "" for c in columns}
    new_row["ticket"] = ticket
    new_row.update(updates)
    rows.append(new_row)
    _write(p, columns, rows)
    return new_row
