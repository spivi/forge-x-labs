"""Tests for scripts/dataset.py -- the ML-ready one-row-per-ticket exporter.

Exercises the estimates x ledger x reviews join, the FIELD_SPECS/FEATURES.md
completeness guarantee, and the fail-soft Parquet path.
"""

from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
_spec = importlib.util.spec_from_file_location("dataset", _SCRIPTS / "dataset.py")
dataset = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dataset)

TIERS = ["haiku", "sonnet", "opus"]


def _estimates():
    return [
        {
            "ticket": "A-1",
            "type": "feature",
            "labels": "",
            "effort": "M",
            "milestone": "M1",
            "risk": "high",
            "area": "api",
            "priority": "P1",
            "recommended_model": "opus",
            "estimate_minutes": "60",
            "scope_changed": "",
            "architectural_deviation": "",
            "clarifying_questions_asked": "2",
            "caused_by": "",
        },
        # B-2 has no actuals and encodes its dims the legacy way (in labels).
        {
            "ticket": "B-2",
            "type": "fix",
            "labels": "effort:S;area:infra",
            "estimate_minutes": "30",
            "recommended_model": "haiku",
        },
    ]


def _ledger():
    row = {
        "duration_sec": "1800",
        "model": "claude-opus-4-8",
        "billed_usd": "0.50",
        "compute_cost_usd": "0.50",
        "input_tokens": "100",
        "output_tokens": "50",
        "cache_creation_tokens": "0",
        "cache_read_tokens": "0",
    }
    return [{"ticket": "A-1", **row}, {"ticket": "A-1", **row}]


def _reviews():
    return [
        {
            "ticket": "A-1",
            "pr": "1",
            "cycles": "2",
            "findings_total": "1",
            "p1": "0",
            "p2": "1",
            "p3": "0",
        }
    ]


# --- build_dataset --------------------------------------------------------


def test_one_row_per_ticket():
    rows = dataset.build_dataset(_estimates(), _ledger(), _reviews(), TIERS)
    by = {r["ticket"]: r for r in rows}
    assert len(rows) == 2
    # A-1: two sessions of 1800s -> 3600s / 60min, estimate 60 -> ratio 1.0
    assert by["A-1"]["session_count"] == 2
    assert by["A-1"]["actual_duration_sec"] == 3600
    assert by["A-1"]["session_min"] == 60.0
    assert by["A-1"]["estimate_ratio"] == 1.0
    assert by["A-1"]["effective_model"] == "opus"
    assert by["A-1"]["risk"] == "high"
    assert by["A-1"]["p2"] == 1
    assert by["A-1"]["suitability_verdict"] in {"underpowered", "overkill", "well-matched"}


def test_dims_fall_back_to_labels_when_no_typed_column():
    rows = dataset.build_dataset(_estimates(), _ledger(), _reviews(), TIERS)
    b2 = {r["ticket"]: r for r in rows}["B-2"]
    assert b2["effort"] == "S"  # parsed from labels "effort:S"
    assert b2["area"] == "infra"


def test_no_actuals_blanks_outcomes():
    rows = dataset.build_dataset(_estimates(), _ledger(), _reviews(), TIERS)
    b2 = {r["ticket"]: r for r in rows}["B-2"]
    assert b2["actual_duration_sec"] == 0
    assert b2["session_count"] == 0
    assert b2["estimate_ratio"] == ""  # no actual -> ratio undefined


def test_ticketless_estimate_row_skipped():
    rows = dataset.build_dataset([{"ticket": "", "type": "feature"}], [], [], TIERS)
    assert rows == []


# --- FIELD_SPECS / FEATURES.md completeness -------------------------------


def test_field_specs_match_columns():
    assert [s[0] for s in dataset.FIELD_SPECS] == dataset.COLUMNS


def test_every_emitted_column_is_documented():
    rows = dataset.build_dataset(_estimates(), _ledger(), _reviews(), TIERS)
    assert set(rows[0].keys()) == set(dataset.COLUMNS)


def test_features_doc_renders_all_columns():
    md = dataset.render_features_md()
    for col in dataset.COLUMNS:
        assert f"`{col}`" in md


# --- writers --------------------------------------------------------------


def test_write_csv_header_is_columns(tmp_path):
    rows = dataset.build_dataset(_estimates(), _ledger(), _reviews(), TIERS)
    out = tmp_path / "dataset.csv"
    dataset.write_csv(rows, out)
    with out.open(newline="") as f:
        header = next(csv.reader(f))
    assert header == dataset.COLUMNS


def test_parquet_failsoft_without_pyarrow(monkeypatch, tmp_path):
    # Force `import pyarrow` to raise -> write_parquet must return False, not crash.
    monkeypatch.setitem(sys.modules, "pyarrow", None)
    assert dataset.write_parquet([{"ticket": "A-1"}], tmp_path / "d.parquet") is False
