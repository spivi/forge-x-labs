"""Tests for scripts/debrief.py -- the calibration + model-suitability engine.

Focuses on the analytical core: aggregating actuals, joining into runs,
classifying model suitability, and the empirical-Bayes calibration math.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
_spec = importlib.util.spec_from_file_location("debrief", _SCRIPTS / "debrief.py")
debrief = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(debrief)

TIERS = ["haiku", "sonnet", "opus"]


# --- sum_actuals ----------------------------------------------------------


def test_sum_actuals_aggregates_duration_and_sessions():
    ledger = [
        {
            "ticket": "A-1",
            "duration_sec": "600",
            "billed_usd": "0.10",
            "compute_cost_usd": "0.10",
            "model": "claude-sonnet-4-6",
            "input_tokens": "100",
            "output_tokens": "50",
            "cache_creation_tokens": "0",
            "cache_read_tokens": "0",
        },
        {
            "ticket": "A-1",
            "duration_sec": "300",
            "billed_usd": "0.05",
            "compute_cost_usd": "0.05",
            "model": "claude-sonnet-4-6",
            "input_tokens": "100",
            "output_tokens": "50",
            "cache_creation_tokens": "0",
            "cache_read_tokens": "0",
        },
    ]
    actuals = debrief.sum_actuals(ledger)
    assert actuals["A-1"]["duration_sec"] == 900
    assert actuals["A-1"]["sessions"] == 2
    assert actuals["A-1"]["cost_usd"] == pytest.approx(0.15)
    assert actuals["A-1"]["tokens_in"] == 200
    assert actuals["A-1"]["tokens_out"] == 100


def test_sum_actuals_ignores_bad_numbers():
    ledger = [
        {
            "ticket": "A-1",
            "duration_sec": "",
            "billed_usd": "x",
            "model": "",
            "input_tokens": "",
            "output_tokens": "",
            "cache_creation_tokens": "",
            "cache_read_tokens": "",
        }
    ]
    actuals = debrief.sum_actuals(ledger)
    assert actuals["A-1"]["duration_sec"] == 0
    assert actuals["A-1"]["cost_usd"] == 0.0


def test_effective_model_picks_highest_tier():
    assert (
        debrief.effective_model(
            ["claude-haiku-4-5", "claude-opus-4-8", "claude-sonnet-4-6"], TIERS
        )
        == "opus"
    )


# --- build_runs -----------------------------------------------------------


def test_build_runs_computes_ratio():
    estimates = [
        {
            "ticket": "A-1",
            "estimate_minutes": "60",
            "type": "feature",
            "labels": "effort:M",
            "recommended_model": "sonnet",
            "scope_changed": "",
        }
    ]
    actuals = {
        "A-1": {
            "duration_sec": 5400,
            "sessions": 1,
            "cost_usd": 0.2,
            "models": ["claude-sonnet-4-6"],
            "tokens_in": 10,
            "tokens_out": 5,
        }
    }
    runs = debrief.build_runs(estimates, actuals, TIERS)
    assert len(runs) == 1
    # 5400s = 90 min, estimate 60 -> ratio 1.5
    assert runs[0]["actual_min"] == pytest.approx(90.0)
    assert runs[0]["ratio"] == pytest.approx(1.5)
    assert runs[0]["effort"] == "M"


def test_build_runs_skips_unmatched_or_zero_estimate():
    estimates = [
        {"ticket": "A-1", "estimate_minutes": "0", "type": "feature", "labels": ""},
        {"ticket": "A-2", "estimate_minutes": "60", "type": "fix", "labels": ""},
    ]
    actuals = {
        "A-2": {
            "duration_sec": 3600,
            "sessions": 1,
            "cost_usd": 0.0,
            "models": [],
            "tokens_in": 0,
            "tokens_out": 0,
        }
    }
    runs = debrief.build_runs(estimates, actuals, TIERS)
    assert [r["ticket"] for r in runs] == ["A-2"]  # A-1 zero estimate dropped


def test_build_runs_prefers_typed_columns():
    # Typed effort/risk/area win over the stale labels string.
    estimates = [
        {
            "ticket": "A-1",
            "estimate_minutes": "60",
            "type": "feature",
            "labels": "effort:M",
            "effort": "XL",
            "risk": "high",
            "area": "api",
            "recommended_model": "sonnet",
            "scope_changed": "",
        }
    ]
    actuals = {
        "A-1": {
            "duration_sec": 3600,
            "sessions": 1,
            "cost_usd": 0.2,
            "models": ["claude-sonnet-4-6"],
            "tokens_in": 10,
            "tokens_out": 5,
        }
    }
    run = debrief.build_runs(estimates, actuals, TIERS)[0]
    assert run["effort"] == "XL"
    assert run["risk"] == "high"
    assert run["area"] == "api"


def test_build_runs_falls_back_to_labels_for_dims():
    estimates = [
        {
            "ticket": "A-1",
            "estimate_minutes": "60",
            "type": "feature",
            "labels": "effort:L;risk:low;area:infra",
            "recommended_model": "sonnet",
        }
    ]
    actuals = {
        "A-1": {
            "duration_sec": 3600,
            "sessions": 1,
            "cost_usd": 0.0,
            "models": [],
            "tokens_in": 0,
            "tokens_out": 0,
        }
    }
    run = debrief.build_runs(estimates, actuals, TIERS)[0]
    assert (run["effort"], run["risk"], run["area"]) == ("L", "low", "infra")


def test_dims_emits_risk_and_area_when_present():
    run = {"type": "feature", "effort": "M", "risk": "high", "area": "api"}
    dims = debrief._dims(run)
    assert dims == ["type:feature", "label:effort:M", "label:risk:high", "label:area:api"]


def test_dims_omits_blank_dims():
    run = {"type": "feature", "effort": "M", "risk": "", "area": ""}
    assert debrief._dims(run) == ["type:feature", "label:effort:M"]


def test_calibration_learns_risk_dimension():
    runs = [
        {
            "type": "feature",
            "effort": "M",
            "risk": "high",
            "area": "",
            "ratio": 2.0,
            "scope_changed": False,
        }
        for _ in range(3)
    ]
    cal = debrief.compute_calibration(runs, min_samples=3)
    assert "label:risk:high" in cal["factors"]


# --- classify_suitability -------------------------------------------------


def _run(ratio, sessions, model, effort="M"):
    return {
        "ratio": ratio,
        "sessions": sessions,
        "effective_model": model,
        "recommended_model": model,
        "effort": effort,
        "type": "feature",
    }


def test_suitability_underpowered_uptiers():
    out = debrief.classify_suitability(_run(2.0, 1, "sonnet"), 0, 0, TIERS)
    assert out["verdict"] == "underpowered"
    assert TIERS.index(out["suggested_model"]) > TIERS.index("sonnet")


def test_suitability_overkill_downtiers_when_clean():
    out = debrief.classify_suitability(_run(0.3, 1, "opus"), 0, 0, TIERS)
    assert out["verdict"] == "overkill"
    assert TIERS.index(out["suggested_model"]) < TIERS.index("opus")


def test_suitability_overkill_blocked_by_p1():
    # Cheap+fast but had a P1 finding -> not safe to downtier.
    out = debrief.classify_suitability(_run(0.3, 1, "opus"), 1, 0, TIERS)
    assert out["verdict"] != "overkill"


def test_suitability_well_matched_default():
    out = debrief.classify_suitability(_run(1.0, 1, "sonnet"), 0, 0, TIERS)
    assert out["verdict"] == "well-matched"


# --- compute_calibration --------------------------------------------------


def test_calibration_shrinks_toward_prior():
    # Four feature runs all at ratio 0.5. Shrunk = (4*0.5 + 3*1.0)/(4+3) = 5/7 ~= 0.714
    runs = [
        {"type": "feature", "effort": "M", "ratio": 0.5, "scope_changed": False} for _ in range(4)
    ]
    cal = debrief.compute_calibration(runs, min_samples=3)
    f = cal["factors"]["type:feature"]
    assert f["samples"] == 4
    assert f["factor"] == pytest.approx(5 / 7, abs=0.01)


def test_calibration_excludes_scope_changed():
    runs = [
        {"type": "feature", "effort": "M", "ratio": 0.5, "scope_changed": True},
        {"type": "feature", "effort": "M", "ratio": 0.5, "scope_changed": True},
    ]
    cal = debrief.compute_calibration(runs, min_samples=1)
    assert "type:feature" not in cal["factors"]


def test_calibration_clamped():
    runs = [
        {"type": "x", "effort": "M", "ratio": 100.0, "scope_changed": False} for _ in range(10)
    ]
    cal = debrief.compute_calibration(runs, min_samples=1, clamp=(0.25, 4.0))
    assert cal["factors"]["type:x"]["factor"] <= 4.0


# --- recommend_models -----------------------------------------------------


def test_pipeline_closes_loop(tmp_path, monkeypatch):
    """Seed estimates + ledger, run the full pipeline, assert it learns a factor
    and routes the model -- the closed loop end to end."""
    est = tmp_path / "estimates.csv"
    est.write_text(
        "ticket,estimate_minutes,type,labels,priority,recommended_model,agent,"
        "started_at,status,scope_changed,architectural_deviation,"
        "clarifying_questions_asked,caused_by\n"
        + "".join(f"FEAT-{i},120,feature,effort:M,,opus,,,done,,,,\n" for i in range(4))
    )
    # Each ticket actually took ~30 min (1800s) on opus, clean & fast -> overkill,
    # and ratio 0.25 -> estimator over-predicts features.
    ledger = tmp_path / "cost-ledger.csv"
    ledger.write_text(
        "timestamp,agent,session_id,provider,model,input_tokens,output_tokens,"
        "cache_creation_tokens,cache_read_tokens,compute_cost_usd,billing_type,"
        "billed_usd,ticket,session_start,session_end,duration_sec\n"
        + "".join(
            f"t,developer,s{i},anthropic,claude-opus-4-8,1000,500,0,0,0.50,api,"
            f"0.50,FEAT-{i},,,1800\n"
            for i in range(4)
        )
    )
    reviews = tmp_path / "reviews.csv"
    reviews.write_text(
        "ticket,pr,provider,reviewed_at,cycles,findings_total,p1,p2,p3,categories,fix_commit_count\n"
    )
    seed = tmp_path / "base-estimates.yml"
    seed.write_text("effort_floor:\n  M: sonnet\n")

    monkeypatch.setattr(debrief, "_ESTIMATES", est)
    monkeypatch.setattr(debrief, "_LEDGER", ledger)
    monkeypatch.setattr(debrief, "_REVIEWS", reviews)
    monkeypatch.setattr(debrief, "_SEED", seed)
    monkeypatch.setattr(debrief, "_CALIBRATION", tmp_path / "calibration.json")
    monkeypatch.setattr(debrief, "_MODEL_POLICY", tmp_path / "model-policy.json")
    monkeypatch.setattr(debrief, "_RECOMMENDATIONS", tmp_path / "recommendations.md")
    monkeypatch.setattr(debrief, "_DATASET", tmp_path / "dataset.csv")
    monkeypatch.setattr(debrief, "_FEATURES", tmp_path / "FEATURES.md")

    result = debrief.run_debrief(dry_run=False)

    # Learned that features over-predict (factor < 1.0).
    assert result["calibration"]["factors"]["type:feature"]["factor"] < 1.0
    # Learned that opus is overkill for M features -> routed down to the sonnet floor.
    rec = result["model_policy"]["learned"]["type:feature"]["recommended_model"]
    assert rec == "sonnet"
    # Files written -- including the ML-ready dataset (closed loop end to end).
    assert (tmp_path / "calibration.json").exists()
    assert (tmp_path / "model-policy.json").exists()
    assert (tmp_path / "dataset.csv").exists()
    assert (tmp_path / "FEATURES.md").exists()
    dataset_lines = (tmp_path / "dataset.csv").read_text().splitlines()
    assert dataset_lines[0].startswith("ticket,type,effort,milestone,risk,area")
    assert len(dataset_lines) == 5  # header + 4 FEAT rows
    # estimator now consumes the learned factor for the next estimate.
    import importlib.util

    espec = importlib.util.spec_from_file_location("estimator2", _SCRIPTS / "estimator.py")
    estimator = importlib.util.module_from_spec(espec)
    espec.loader.exec_module(estimator)
    cal = json.loads((tmp_path / "calibration.json").read_text())
    seed_dict = {"base_minutes": {"feature": 120, "default": 60}, "clamp_minutes": [5, 480]}
    next_estimate = estimator.estimate_minutes("feature", "M", seed_dict, cal)
    assert next_estimate < 120  # sharper than the cold-start seed


def test_recommend_models_downtiers_on_majority_overkill():
    runs = [_run(0.3, 1, "opus") for _ in range(4)]
    for r in runs:
        r["scope_changed"] = False
        r["cost_usd"] = 0.2
    policy = debrief.recommend_models(
        runs, min_samples=3, tiers=TIERS, effort_floor={"M": "sonnet"}
    )
    rec = policy["learned"]["type:feature"]["recommended_model"]
    assert TIERS.index(rec) < TIERS.index("opus")
    assert TIERS.index(rec) >= TIERS.index("sonnet")  # never below the floor


# ---------------------------------------------------------------------------
# cli_routing_report (harness-router / Gemini ledger summary, DT-7)
# ---------------------------------------------------------------------------


def test_cli_routing_report_missing_ledger(tmp_path):
    out = debrief.cli_routing_report(tmp_path)
    assert "not found" in out


def test_cli_routing_report_header_only_is_empty(tmp_path):
    (tmp_path / "cli-routing.csv").write_text(
        "ts_iso,ticket,operation,provider,input_chars,est_input_tokens,"
        "output_chars,est_output_tokens,wall_clock_ms,fallback,claude_skipped\n"
    )
    assert "empty" in debrief.cli_routing_report(tmp_path)


def test_cli_routing_report_summarizes_and_flags_thresholds(tmp_path):
    header = (
        "ts_iso,ticket,operation,provider,input_chars,est_input_tokens,"
        "output_chars,est_output_tokens,wall_clock_ms,fallback,claude_skipped\n"
    )
    # One fast clean call + one slow call (>5000ms) to trip the latency threshold.
    rows = (
        "2026-06-01T10:00:00Z,A-1,summarize-ci,gemini,100,25,40,10,800,0,1\n"
        "2026-06-01T10:01:00Z,A-2,summarize-diff,gemini,200,50,80,20,6000,0,1\n"
    )
    (tmp_path / "cli-routing.csv").write_text(header + rows)
    out = debrief.cli_routing_report(tmp_path)
    assert "2 total calls" in out
    assert "[summarize-ci]" in out and "[summarize-diff]" in out
    assert "CALLS TO ACTION" in out  # the 6000ms call trips the >5000ms threshold


def test_cli_routing_thresholds_fallback_rate():
    actions = debrief._cli_routing_thresholds("summarize-ci", avg_ms=100.0, fallback_rate=0.5)
    assert any("fallback rate" in a for a in actions)


# ---------------------------------------------------------------------------
# In-session AI review gate (record + audit, DT-10)
# ---------------------------------------------------------------------------


def test_review_status_state_clean_pass():
    v = {"verdict": "PASS", "counts": {"p1": 0, "p2": 1, "p3": 0}, "findings": []}
    assert debrief.review_status_state(v) == "success"


def test_review_status_state_fail_on_p1_count():
    v = {"verdict": "PASS", "counts": {"p1": 1}, "findings": []}
    assert debrief.review_status_state(v) == "failure"


def test_review_status_state_fail_closed_on_inconsistent_finding():
    # verdict says PASS + counts.p1=0, but a findings[] entry is P1 → fail closed.
    v = {
        "verdict": "PASS",
        "counts": {"p1": 0, "p2": 0, "p3": 0},
        "findings": [{"severity": "P1", "file": "a.py", "title": "vuln"}],
    }
    assert debrief.review_status_state(v) == "failure"


def test_review_status_state_fail_on_fail_verdict():
    assert debrief.review_status_state({"verdict": "FAIL", "counts": {}}) == "failure"


def test_record_review_from_verdict_writes_row(tmp_path):
    # Point the writer at a temp reviews.csv via the module-level _REVIEWS override.
    import review_capture  # noqa: PLC0415

    reviews = tmp_path / "reviews.csv"
    verdict = {
        "ticket": "ABC-1",
        "pr": 5,
        "reviewer_model": "opus",
        "verdict": "PASS",
        "counts": {"p1": 0, "p2": 1, "p3": 0, "total": 1},
        "findings": [{"severity": "P2", "category": "correctness", "file": "a.py", "line": 3}],
        "cycle": 2,
    }
    row = debrief.record_review_from_verdict(tmp_path, verdict, dry_run=True)
    assert row["ticket"] == "ABC-1"
    assert row["provider"] == "claude-opus"  # opus reviewer → claude-opus
    assert row["p2"] == "1"
    assert row["cycles"] == "2"
    assert "correctness:1" in row["categories"]
    # dry_run=True → no file written
    assert not reviews.exists()
    # Build the row directly to confirm it round-trips through review_capture
    assert review_capture.build_review_row("ABC-1", 5, "claude")["ticket"] == "ABC-1"


def test_render_review_comment_includes_findings_and_insights():
    v = {
        "verdict": "FAIL",
        "reviewer_model": "sonnet",
        "counts": {"p1": 1, "p2": 0, "p3": 0},
        "findings": [
            {"severity": "P1", "file": "a.py", "line": 9, "title": "boom", "fix": "guard it"}
        ],
        "process_insights": {"spec_clarity": "vague", "label_accuracy": "ok"},
        "cycle": 1,
    }
    out = debrief.render_review_comment(v)
    assert "AI Review Gate — FAIL" in out
    assert "❌" in out
    assert "`a.py:9`" in out
    assert "guard it" in out
    assert "spec_clarity" in out


def test_post_review_audit_dry_run_no_network():
    v = {
        "ticket": "ABC-1",
        "pr": 5,
        "verdict": "PASS",
        "counts": {},
        "head_sha": "deadbeef",
        "cycle": 1,
    }
    out = debrief.post_review_audit(v, "acme", "widget", 5, dry_run=True)
    assert out["posted"] is False
    assert out["state"] == "success"
    assert out["head_sha"] == "deadbeef"
    assert out["comment_len"] > 0
