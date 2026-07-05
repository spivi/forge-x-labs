"""Tests for scripts/ci_latency.py -- CI wall-clock instrumentation.

The pure compute + parse helpers and the append writer are tested directly; the
gh-API fetch is network-bound (excluded from coverage).
"""

from __future__ import annotations

import csv
import importlib.util
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
_spec = importlib.util.spec_from_file_location("ci_latency", _SCRIPTS / "ci_latency.py")
cl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cl)

RUNS = [
    {
        "name": "lint",
        "started_at": "2026-01-01T00:00:00Z",
        "completed_at": "2026-01-01T00:01:00Z",
        "conclusion": "success",
    },
    {
        "name": "test",
        "started_at": "2026-01-01T00:00:30Z",
        "completed_at": "2026-01-01T00:03:00Z",
        "conclusion": "success",
    },
]


# --- compute_ci_wall_clock ------------------------------------------------


def test_compute_wall_clock_and_slowest():
    m = cl.compute_ci_wall_clock(RUNS)
    assert m["ci_wall_clock_s"] == 180.0  # 00:00:00 -> 00:03:00
    assert m["jobs_observed"] == 2
    assert m["slowest_job"] == "test"


def test_compute_skips_cancelled():
    runs = [
        *RUNS,
        {
            "name": "flaky",
            "started_at": "2025-12-31T00:00:00Z",
            "completed_at": "2026-01-02T00:00:00Z",
            "conclusion": "cancelled",
        },
    ]
    m = cl.compute_ci_wall_clock(runs)
    assert m["jobs_observed"] == 2  # cancelled excluded from the span
    assert m["ci_wall_clock_s"] == 180.0


def test_compute_none_when_empty():
    assert cl.compute_ci_wall_clock([]) is None


def test_compute_none_when_timestamps_missing():
    assert cl.compute_ci_wall_clock([{"name": "x", "conclusion": "success"}]) is None


def test_parse_iso_handles_z_and_invalid():
    assert cl._parse_iso("2026-01-01T00:00:00Z") is not None
    assert cl._parse_iso("nonsense") is None
    assert cl._parse_iso("") is None


# --- append_ci_latency_row ------------------------------------------------


def test_append_row_creates_header(tmp_path):
    p = tmp_path / "ci-latency.csv"
    cl.append_ci_latency_row(
        "ABC-1",
        42,
        "abc123",
        {"ci_wall_clock_s": 180.0, "jobs_observed": 2, "slowest_job": "test"},
        csv_path=p,
    )
    assert p.read_text().splitlines()[0].split(",") == cl.CI_LATENCY_FIELDNAMES
    with p.open(newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["ticket"] == "ABC-1"
    assert rows[0]["ci_wall_clock_s"] == "180.0"
    assert rows[0]["slowest_job"] == "test"


def test_append_row_is_append_only(tmp_path):
    p = tmp_path / "ci-latency.csv"
    m = {"ci_wall_clock_s": 1.0, "jobs_observed": 1, "slowest_job": "a"}
    cl.append_ci_latency_row("A-1", 1, "s1", m, csv_path=p)
    cl.append_ci_latency_row("A-2", 2, "s2", m, csv_path=p)
    with p.open(newline="") as f:
        rows = list(csv.DictReader(f))
    assert [r["ticket"] for r in rows] == ["A-1", "A-2"]
