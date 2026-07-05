"""Tests for scripts/tracker.py and the canonical CSV store.

The CSV store (estimates.csv) is the source of truth; the `none` backend mirrors
nowhere. These tests exercise the canonical path end to end with tmp files.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


store = _load("estimates_store", "trackers/store.py")
tracker = _load("tracker", "tracker.py")

HEADER = (
    "ticket,estimate_minutes,type,labels,effort,milestone,risk,area,priority,"
    "recommended_model,agent,started_at,status,scope_changed,"
    "architectural_deviation,clarifying_questions_asked,caused_by\n"
)

# The pre-typed-dimensions 13-col header, for migration tests.
LEGACY_HEADER = (
    "ticket,estimate_minutes,type,labels,priority,recommended_model,agent,"
    "started_at,status,scope_changed,architectural_deviation,"
    "clarifying_questions_asked,caused_by\n"
)


@pytest.fixture
def csv_path(tmp_path) -> Path:
    p = tmp_path / "estimates.csv"
    p.write_text(HEADER)
    return p


# --- store ----------------------------------------------------------------


def test_upsert_appends_new_row(csv_path):
    store.upsert(csv_path, "ABC-1", estimate_minutes="120", type="feature")
    rows = store.read_rows(csv_path)
    assert len(rows) == 1
    assert rows[0]["ticket"] == "ABC-1"
    assert rows[0]["estimate_minutes"] == "120"
    assert rows[0]["type"] == "feature"


def test_upsert_updates_existing_row(csv_path):
    store.upsert(csv_path, "ABC-1", estimate_minutes="120")
    store.upsert(csv_path, "ABC-1", estimate_minutes="90", status="in_progress")
    rows = store.read_rows(csv_path)
    assert len(rows) == 1
    assert rows[0]["estimate_minutes"] == "90"
    assert rows[0]["status"] == "in_progress"


def test_upsert_preserves_other_fields(csv_path):
    store.upsert(csv_path, "ABC-1", estimate_minutes="120", type="feature")
    store.upsert(csv_path, "ABC-1", status="done")
    row = store.get_row(csv_path, "ABC-1")
    assert row["type"] == "feature"  # untouched
    assert row["status"] == "done"


def test_get_row_missing_returns_none(csv_path):
    assert store.get_row(csv_path, "NOPE-9") is None


def test_quoting_roundtrips_commas(csv_path):
    store.upsert(csv_path, "ABC-1", labels="effort:M;area:a,b")
    assert store.get_row(csv_path, "ABC-1")["labels"] == "effort:M;area:a,b"


# --- typed dimensions + migration -----------------------------------------


def test_upsert_writes_typed_columns(csv_path):
    store.upsert(csv_path, "ABC-1", effort="L", milestone="M1", risk="high", area="api")
    row = store.get_row(csv_path, "ABC-1")
    assert row["effort"] == "L"
    assert row["milestone"] == "M1"
    assert row["risk"] == "high"
    assert row["area"] == "api"


def test_read_legacy_csv_no_crash(tmp_path):
    p = tmp_path / "legacy.csv"
    p.write_text(LEGACY_HEADER + "ABC-1,60,feature,effort:L,,sonnet,,,,,,,\n")
    rows = store.read_rows(p)
    assert rows[0]["ticket"] == "ABC-1"
    assert "effort" not in rows[0]  # typed column simply absent, no exception


def test_migrate_backfills_typed_from_labels(tmp_path):
    p = tmp_path / "estimates.csv"
    p.write_text(
        LEGACY_HEADER
        + "ABC-1,60,feature,effort:L;area:api;risk:high;milestone:M1,,opus,,,planned,,,,\n"
    )
    assert tracker.migrate_estimates_header(p) is True
    row = store.get_row(p, "ABC-1")
    assert row["effort"] == "L"
    assert row["area"] == "api"
    assert row["risk"] == "high"
    assert row["milestone"] == "M1"
    assert row["estimate_minutes"] == "60"  # untouched
    # Header is now the canonical 17-col set, and a second run is a no-op.
    assert store._columns(p) == list(store.COLUMNS)
    assert tracker.migrate_estimates_header(p) is False


def test_migrate_noop_on_canonical(csv_path):
    store.upsert(csv_path, "ABC-1", effort="L")
    assert tracker.migrate_estimates_header(csv_path) is False


def test_refresh_prefers_typed_effort_over_labels(csv_path):
    # Typed effort=L must win over the stale labels "effort:M" -> opus floor (L), not sonnet (M).
    store.upsert(
        csv_path,
        "ABC-1",
        estimate_minutes="999",
        type="feature",
        labels="effort:M",
        effort="L",
        recommended_model="haiku",
        status="planned",
    )
    seed = {
        "model_tiers": ["haiku", "sonnet", "opus"],
        "effort_floor": {"M": "sonnet", "L": "opus"},
        "default_floor": "sonnet",
        "base_minutes": {"feature": 120, "default": 60},
        "type_model": {"default": "sonnet"},
        "clamp_minutes": [5, 480],
    }
    tracker.refresh(csv_path, seed=seed, calibration={}, policy={})
    assert store.get_row(csv_path, "ABC-1")["recommended_model"] == "opus"  # L floor


# --- ready gate -----------------------------------------------------------


def test_ready_false_when_missing(csv_path):
    ok, _ = tracker.is_ready(csv_path, "ABC-1")
    assert ok is False


def test_ready_false_without_estimate(csv_path):
    store.upsert(csv_path, "ABC-1", recommended_model="sonnet", status="planned")
    ok, reason = tracker.is_ready(csv_path, "ABC-1")
    assert ok is False
    assert "estimate" in reason.lower()


def test_ready_false_without_model(csv_path):
    store.upsert(csv_path, "ABC-1", estimate_minutes="60", status="planned")
    ok, reason = tracker.is_ready(csv_path, "ABC-1")
    assert ok is False
    assert "model" in reason.lower()


def test_ready_true_when_planned_estimate_and_model(csv_path):
    store.upsert(
        csv_path,
        "ABC-1",
        estimate_minutes="60",
        recommended_model="sonnet",
        status="planned",
    )
    ok, _ = tracker.is_ready(csv_path, "ABC-1")
    assert ok is True


def test_ready_false_when_status_done(csv_path):
    store.upsert(
        csv_path,
        "ABC-1",
        estimate_minutes="60",
        recommended_model="sonnet",
        status="done",
    )
    ok, reason = tracker.is_ready(csv_path, "ABC-1")
    assert ok is False
    assert "status" in reason.lower()


# --- refresh (idempotent re-seed from immutable base) ---------------------


def test_refresh_reseeds_planned_rows(csv_path, tmp_path):
    # planned feature with stale estimate; calibration halves features.
    store.upsert(
        csv_path,
        "ABC-1",
        estimate_minutes="999",
        type="feature",
        labels="effort:M",
        recommended_model="opus",
        status="planned",
    )
    seed = {
        "model_tiers": ["haiku", "sonnet", "opus"],
        "effort_floor": {"M": "sonnet"},
        "default_floor": "sonnet",
        "base_minutes": {"feature": 120, "default": 60},
        "type_model": {"default": "sonnet"},
        "clamp_minutes": [5, 480],
    }
    calibration = {"factors": {"type:feature": {"factor": 0.5}}}
    changed = tracker.refresh(csv_path, seed=seed, calibration=calibration, policy={})
    row = store.get_row(csv_path, "ABC-1")
    assert row["estimate_minutes"] == "60"  # 120 * 0.5
    assert row["recommended_model"] == "sonnet"  # floor for M
    assert "ABC-1" in changed


def test_refresh_idempotent(csv_path):
    # Stale estimate so the first run changes it; the second must be a no-op.
    store.upsert(
        csv_path,
        "ABC-1",
        estimate_minutes="999",
        type="feature",
        labels="effort:M",
        recommended_model="opus",
        status="planned",
    )
    seed = {
        "model_tiers": ["haiku", "sonnet", "opus"],
        "effort_floor": {"M": "sonnet"},
        "default_floor": "sonnet",
        "base_minutes": {"feature": 120, "default": 60},
        "type_model": {"default": "sonnet"},
        "clamp_minutes": [5, 480],
    }
    first = tracker.refresh(csv_path, seed=seed, calibration={}, policy={})
    second = tracker.refresh(csv_path, seed=seed, calibration={}, policy={})
    assert "ABC-1" in first  # 999->120, opus->sonnet
    assert second == []  # second run is a no-op


def test_refresh_skips_in_progress(csv_path):
    store.upsert(
        csv_path,
        "ABC-1",
        estimate_minutes="999",
        type="feature",
        labels="effort:M",
        recommended_model="opus",
        status="in_progress",
    )
    seed = {
        "model_tiers": ["haiku", "sonnet", "opus"],
        "effort_floor": {"M": "sonnet"},
        "default_floor": "sonnet",
        "base_minutes": {"feature": 120, "default": 60},
        "type_model": {"default": "sonnet"},
        "clamp_minutes": [5, 480],
    }
    changed = tracker.refresh(csv_path, seed=seed, calibration={}, policy={})
    assert changed == []
    assert store.get_row(csv_path, "ABC-1")["estimate_minutes"] == "999"  # untouched
