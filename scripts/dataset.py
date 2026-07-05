#!/usr/bin/env python3
"""ML-ready dataset exporter: one tidy row per ticket.

Joins the planning ledger (kpis/estimates.csv) with aggregated actuals
(cost-ledger.csv) and review outcomes (kpis/reviews.csv) into a single wide row
per ticket -- every typed label as a FEATURE column, every measured outcome as an
OUTCOME column -- ready for offline ML / analysis. Reuses debrief's aggregation
(sum_actuals / effective_model / classify_suitability) so the join logic lives in
exactly one place.

Writes .dev-context/kpis/dataset.csv always; Parquet only when pyarrow is present
(fail-soft). FEATURES.md (the data dictionary) is generated from FIELD_SPECS, so
it can never drift from the exporter -- a test guards that every emitted column is
documented.

CLI:
    python scripts/dataset.py [--parquet] [--out PATH] [--no-features-doc]
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import debrief  # noqa: E402  (sibling module; reuse its aggregation + IO)

_DEV = _REPO / ".dev-context"
_ESTIMATES = _DEV / "kpis" / "estimates.csv"
_REVIEWS = _DEV / "kpis" / "reviews.csv"
_LEDGER = _DEV / "cost-ledger.csv"
_DATASET = _DEV / "kpis" / "dataset.csv"
_FEATURES_DOC = _DEV / "kpis" / "FEATURES.md"

# (name, dtype, source, role, notes) -- the SINGLE source of truth for both the
# exporter's column order and the generated FEATURES.md data dictionary. Adding a
# new taxonomy dimension? Add its typed column to store.COLUMNS + a row here.
FIELD_SPECS: list[tuple[str, str, str, str, str]] = [
    # --- id ---
    ("ticket", "str", "estimates.csv", "id", "ticket key (join key)"),
    # --- features (planning labels) ---
    ("type", "str", "estimates.csv", "feature", "feature|fix|tweak|refactor|..."),
    ("effort", "str", "estimates.csv", "feature", "S|M|L|XL (typed, labels fallback)"),
    ("milestone", "str", "estimates.csv", "feature", "open vocabulary"),
    ("risk", "str", "estimates.csv", "feature", "low|medium|high"),
    ("area", "str", "estimates.csv", "feature", "open vocabulary (api|ui|infra|...)"),
    ("priority", "str", "estimates.csv", "feature", "open vocabulary"),
    ("recommended_model", "str", "estimates.csv", "feature", "planned cheapest-sufficient model"),
    ("estimate_minutes", "int", "estimates.csv", "feature", "planned wall-clock minutes"),
    ("scope_changed", "int", "estimates.csv", "feature", "1 if folded/partial, else 0"),
    ("architectural_deviation", "int", "estimates.csv", "feature", "1 if deviated, else 0"),
    ("clarifying_questions_asked", "int", "estimates.csv", "feature", "spec-quality signal"),
    ("caused_by", "str", "estimates.csv", "feature", "originating ticket (bugs only)"),
    # --- outcomes (measured actuals) ---
    ("actual_duration_sec", "int", "cost-ledger.csv", "outcome", "summed session seconds"),
    ("session_count", "int", "cost-ledger.csv", "outcome", "ledger rows for the ticket"),
    ("session_min", "float", "cost-ledger.csv", "outcome", "actual wall-clock minutes"),
    ("tokens_in", "int", "cost-ledger.csv", "outcome", "input+cache_creation+cache_read"),
    ("tokens_out", "int", "cost-ledger.csv", "outcome", "output tokens"),
    ("cost_usd", "float", "cost-ledger.csv", "outcome", "summed cost (billed||compute)"),
    ("effective_model", "str", "cost-ledger.csv", "outcome", "highest-tier model actually used"),
    ("estimate_ratio", "float", "derived", "outcome", "actual_min / estimate_minutes"),
    # --- outcomes (review) ---
    ("review_cycles", "int", "reviews.csv", "outcome", "max push->review rounds"),
    ("findings_total", "int", "reviews.csv", "outcome", "all review findings"),
    ("p1", "int", "reviews.csv", "outcome", "critical findings"),
    ("p2", "int", "reviews.csv", "outcome", "major findings"),
    ("p3", "int", "reviews.csv", "outcome", "minor findings"),
    ("review_stale_s", "float", "reviews.csv", "outcome", "review latency seconds (may be blank)"),
    # --- derived verdict ---
    ("suitability_verdict", "str", "derived", "outcome", "underpowered|overkill|well-matched"),
]

COLUMNS: list[str] = [spec[0] for spec in FIELD_SPECS]


# --- aggregation ----------------------------------------------------------


def _reviews_agg(review_rows: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    """Aggregate reviews.csv rows per ticket: summed findings, max cycles, last
    non-blank review_stale_s. Tolerant of the pre-latency 11-col schema."""
    out: dict[str, dict[str, Any]] = {}
    for row in review_rows:
        ticket = (row.get("ticket") or "").strip()
        if not ticket:
            continue
        agg = out.setdefault(
            ticket,
            {
                "review_cycles": 0,
                "findings_total": 0,
                "p1": 0,
                "p2": 0,
                "p3": 0,
                "review_stale_s": "",
            },
        )
        agg["review_cycles"] = max(agg["review_cycles"], debrief._num(row.get("cycles"), int, 0))
        for key in ("findings_total", "p1", "p2", "p3"):
            agg[key] += debrief._num(row.get(key), int, 0)
        stale = row.get("review_stale_s")
        if stale not in (None, ""):
            agg["review_stale_s"] = debrief._num(stale, float, "")
    return out


def _feature(est: dict[str, str], col: str, prefix: str) -> str:
    """Typed column wins; fall back to parsing the legacy `labels` string."""
    val = (est.get(col) or "").strip()
    if val:
        return val
    labels = est.get("labels") or ""
    if col == "effort":
        return debrief._effort(labels) or ""
    return debrief._label_dim(labels, prefix)


def _b(est: dict[str, str], col: str) -> int:
    """A boolean feature flag as ML-friendly 0/1."""
    return int(debrief._truthy(est.get(col)))


def build_dataset(
    estimate_rows: list[dict[str, str]],
    ledger_rows: list[dict[str, str]],
    review_rows: list[dict[str, str]],
    tiers: list[str],
) -> list[dict[str, Any]]:
    """One tidy row per ticket = planning features + measured outcomes. LEFT join
    on estimates: a ticket with no actuals still emits a row (outcomes blank/zero)."""
    actuals = debrief.sum_actuals(ledger_rows)
    reviews = _reviews_agg(review_rows)
    rows: list[dict[str, Any]] = []
    for est in estimate_rows:
        ticket = (est.get("ticket") or "").strip()
        if not ticket:
            continue
        a = actuals.get(ticket, {})
        r = reviews.get(ticket, {})
        dur = int(a.get("duration_sec", 0) or 0)
        est_min = debrief._num(est.get("estimate_minutes"), float, 0.0)
        ratio = round((dur / 60.0) / est_min, 4) if (est_min > 0 and dur) else ""
        eff_model = debrief.effective_model(a.get("models", []), tiers) or (
            est.get("recommended_model") or ""
        )
        run = {
            "effective_model": eff_model,
            "recommended_model": est.get("recommended_model") or "",
            "ratio": ratio if ratio != "" else 1.0,
            "sessions": a.get("sessions", 1),
            "effort": _feature(est, "effort", "effort:"),
        }
        verdict = debrief.classify_suitability(run, r.get("p1", 0), r.get("p2", 0), tiers)[
            "verdict"
        ]
        rows.append(
            {
                "ticket": ticket,
                "type": est.get("type") or "",
                "effort": _feature(est, "effort", "effort:"),
                "milestone": _feature(est, "milestone", "milestone:"),
                "risk": _feature(est, "risk", "risk:"),
                "area": _feature(est, "area", "area:"),
                "priority": est.get("priority") or "",
                "recommended_model": est.get("recommended_model") or "",
                "estimate_minutes": debrief._num(est.get("estimate_minutes"), int, 0),
                "scope_changed": _b(est, "scope_changed"),
                "architectural_deviation": _b(est, "architectural_deviation"),
                "clarifying_questions_asked": debrief._num(
                    est.get("clarifying_questions_asked"), int, 0
                ),
                "caused_by": est.get("caused_by") or "",
                "actual_duration_sec": dur,
                "session_count": int(a.get("sessions", 0) or 0),
                "session_min": round(dur / 60.0, 2) if dur else 0.0,
                "tokens_in": int(a.get("tokens_in", 0) or 0),
                "tokens_out": int(a.get("tokens_out", 0) or 0),
                "cost_usd": round(float(a.get("cost_usd", 0.0) or 0.0), 4),
                "effective_model": eff_model,
                "estimate_ratio": ratio,
                "review_cycles": r.get("review_cycles", 0),
                "findings_total": r.get("findings_total", 0),
                "p1": r.get("p1", 0),
                "p2": r.get("p2", 0),
                "p3": r.get("p3", 0),
                "review_stale_s": r.get("review_stale_s", ""),
                "suitability_verdict": verdict,
            }
        )
    return rows


# --- writers --------------------------------------------------------------


def write_csv(rows: list[dict[str, Any]], path: str | Path) -> None:
    with Path(path).open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row.get(c, "") for c in COLUMNS})


def write_parquet(rows: list[dict[str, Any]], path: str | Path) -> bool:
    """Write a Parquet file if pyarrow is available. Fail-soft: returns False
    (CSV always succeeds) when pyarrow is not installed."""
    try:
        import pyarrow as pa  # noqa: PLC0415
        import pyarrow.parquet as pq  # noqa: PLC0415
    except ImportError:
        return False
    table = pa.Table.from_pylist([{c: r.get(c) for c in COLUMNS} for r in rows])
    pq.write_table(table, str(path))
    return True


def render_features_md() -> str:
    """Generate the data dictionary from FIELD_SPECS (never hand-edit FEATURES.md)."""
    lines = [
        "# Dataset feature dictionary",
        "",
        "Auto-generated from `scripts/dataset.py::FIELD_SPECS` by `/debrief` "
        "(or `python scripts/dataset.py`). One row per ticket in `kpis/dataset.csv`. "
        "Do not edit by hand.",
        "",
        "| column | type | source | role | notes |",
        "|---|---|---|---|---|",
    ]
    for name, dtype, source, role, notes in FIELD_SPECS:
        lines.append(f"| `{name}` | {dtype} | {source} | {role} | {notes} |")
    return "\n".join(lines) + "\n"


# --- IO + CLI -------------------------------------------------------------


def generate(
    *, parquet: bool = False, out: str | Path | None = None, features_doc: bool = True
) -> list[dict[str, Any]]:
    """Read the canonical CSVs, build the dataset, and write outputs. Fail-soft on
    Parquet. Returns the rows (so callers can introspect)."""
    rows = build_dataset(
        debrief._read_csv(_ESTIMATES),
        debrief._read_csv(_LEDGER),
        debrief._read_csv(_REVIEWS),
        debrief.DEFAULT_TIERS,
    )
    out_path = Path(out) if out else _DATASET
    write_csv(rows, out_path)
    if parquet:
        write_parquet(rows, out_path.with_suffix(".parquet"))
    if features_doc:
        _FEATURES_DOC.write_text(render_features_md())
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export the ML-ready ticket dataset")
    parser.add_argument("--parquet", action="store_true", help="also write .parquet (if pyarrow)")
    parser.add_argument("--out", default=None, help="dataset CSV path (default kpis/dataset.csv)")
    parser.add_argument("--no-features-doc", action="store_true", help="skip FEATURES.md")
    args = parser.parse_args(argv)
    rows = generate(parquet=args.parquet, out=args.out, features_doc=not args.no_features_doc)
    print(f"wrote {len(rows)} rows x {len(COLUMNS)} columns")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
