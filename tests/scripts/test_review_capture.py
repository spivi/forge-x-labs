"""Tests for scripts/review_capture.py.

The quiescence poll is driven by an injected fetch + a fake clock, so the adaptive
backoff / quiet-window logic is exercised deterministically with no network or real
sleeps. The 11->13 reviews.csv migration and row builder are tested directly.
"""

from __future__ import annotations

import csv
import importlib.util
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
_spec = importlib.util.spec_from_file_location("review_capture", _SCRIPTS / "review_capture.py")
rc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rc)


class FakeClock:
    """Deterministic clock: sleep() advances virtual time, now() reads it."""

    def __init__(self) -> None:
        self.t = 0.0

    def now(self) -> float:
        return self.t

    def sleep(self, s: float) -> None:
        self.t += s


# --- poll_review ----------------------------------------------------------


def _one_artifact_fetch(ts="2026-01-01T00:00:01Z"):
    """Returns the artifact once (when newer than the watermark), then nothing."""

    def fetch(watermark):
        if watermark is None or watermark < ts:
            return [{"updated_at": ts}]
        return []

    return fetch


def test_poll_quiesces_after_quiet_window():
    fc = FakeClock()
    res = rc.poll_review(
        _one_artifact_fetch(), quiescence=40, max_wait=300, clock=fc.now, sleep=fc.sleep
    )
    assert res["status"] == rc.QUIESCED
    assert len(res["artifacts"]) == 1
    assert res["first_event_at"] == "2026-01-01T00:00:01Z"
    assert res["review_stale_s"] >= 40


def test_poll_timeout_when_no_artifacts():
    fc = FakeClock()
    res = rc.poll_review(lambda w: [], quiescence=40, max_wait=100, clock=fc.now, sleep=fc.sleep)
    assert res["status"] == rc.TIMEOUT
    assert res["artifacts"] == []
    assert res["review_stale_s"] >= 100


def test_poll_timeout_when_never_quiet():
    # A fresh artifact every round keeps resetting the quiet window -> TIMEOUT.
    state = {"i": 0}

    def fetch(watermark):
        state["i"] += 1
        return [{"updated_at": f"2026-01-01T00:01:{state['i']:02d}Z"}]

    fc = FakeClock()
    res = rc.poll_review(fetch, quiescence=40, max_wait=100, clock=fc.now, sleep=fc.sleep)
    assert res["status"] == rc.TIMEOUT
    assert len(res["artifacts"]) >= 1  # saw artifacts, just never quiesced


# --- migration ------------------------------------------------------------


def test_migrate_11col_to_13col(tmp_path):
    p = tmp_path / "reviews.csv"
    p.write_text(
        ",".join(rc._LEGACY_REVIEW_COLUMNS) + "\n" + "ABC-1,1,codex,t,2,3,0,1,2,logic:1,0\n"
    )
    assert rc.migrate_reviews_header(p) is True
    assert p.read_text().splitlines()[0].split(",") == rc.REVIEW_COLUMNS
    with p.open(newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["ticket"] == "ABC-1"
    assert rows[0]["review_stale_s"] == ""  # back-filled blank
    assert rc.migrate_reviews_header(p) is False  # idempotent


def test_migrate_noop_on_13col(tmp_path):
    p = tmp_path / "reviews.csv"
    p.write_text(",".join(rc.REVIEW_COLUMNS) + "\n")
    assert rc.migrate_reviews_header(p) is False


# --- row builder + append -------------------------------------------------


def test_build_review_row_has_13_columns():
    row = rc.build_review_row(
        "ABC-1",
        42,
        "codex",
        summary={"p1": 1, "cycles": 2, "findings_total": 3, "categories": "logic:1"},
        poll_result={"first_event_at": "2026-01-01T00:00:00Z", "review_stale_s": 12.5},
    )
    assert list(row.keys()) == rc.REVIEW_COLUMNS
    assert row["p1"] == "1"
    assert row["review_stale_s"] == "12.5"
    assert row["review_first_event_at"] == "2026-01-01T00:00:00Z"


def test_append_creates_file_with_13col_header(tmp_path):
    p = tmp_path / "reviews.csv"
    rc.append_review(rc.build_review_row("X-1", 1, "codex"), path=p)
    assert p.read_text().splitlines()[0].split(",") == rc.REVIEW_COLUMNS


def test_append_migrates_legacy_then_writes(tmp_path):
    p = tmp_path / "reviews.csv"
    p.write_text(",".join(rc._LEGACY_REVIEW_COLUMNS) + "\n")
    rc.append_review(rc.build_review_row("ABC-1", 42, "codex", summary={"p1": 0}), path=p)
    assert p.read_text().splitlines()[0].split(",") == rc.REVIEW_COLUMNS
    with p.open(newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1 and rows[0]["ticket"] == "ABC-1"
