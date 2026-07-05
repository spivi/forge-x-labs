"""Tests for scripts/subscription_quota.py -- the subscription quota gate.

Band math + weighting are pure; the gate is exercised with a tmp budgets.yml +
injected usage (no vendor stats source needed).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
_spec = importlib.util.spec_from_file_location(
    "subscription_quota", _SCRIPTS / "subscription_quota.py"
)
sq = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sq)


# --- band math ------------------------------------------------------------


def test_classify_band_thresholds():
    assert sq.classify_band(10) == "OK"
    assert sq.classify_band(70) == "WARN"
    assert sq.classify_band(90) == "CRITICAL"
    assert sq.classify_band(100) == "EXCEEDED"
    assert sq.classify_band(150) == "EXCEEDED"


def test_most_restrictive_band():
    assert sq.most_restrictive_band(["OK", "WARN", "CRITICAL"]) == "CRITICAL"
    assert sq.most_restrictive_band([]) == "OK"
    assert sq.most_restrictive_band(["OK", "EXCEEDED"]) == "EXCEEDED"


def test_compute_quota_draw_weights_opus_heavier():
    # 100 opus tokens (x5) + 100 haiku (x0.2) = 500 + 20 = 520
    draw = sq.compute_quota_draw({"claude-opus-4-8": 100, "claude-haiku-4-5": 100})
    assert draw == 520.0


# --- gate -----------------------------------------------------------------


def _budgets(tmp_path, provider="null", weekly_limit=0):
    p = tmp_path / "budgets.yml"
    prov = "null" if provider == "null" else provider
    p.write_text(
        f"subscription:\n  provider: {prov}\n  window_limit_weekly: {weekly_limit}\n"
        "  window_limit_5h: 1000\n  warn_at_weekly_pct: 70\n  critical_at_weekly_pct: 90\n"
    )
    return p


def test_gate_disabled_when_provider_null(tmp_path):
    report = sq.run_quota_gate(budgets_path=_budgets(tmp_path, provider="null"))
    assert report["enabled"] is False
    assert report["overall_band"] == "OK"


def test_gate_disabled_when_no_usage(tmp_path):
    report = sq.run_quota_gate(budgets_path=_budgets(tmp_path, provider="anthropic"))
    assert report["enabled"] is False
    assert "fail-open" in report["error"]


def test_gate_enabled_computes_weekly_band(tmp_path):
    budgets = _budgets(tmp_path, provider="anthropic", weekly_limit=1000)
    # 200 sonnet tokens (x1) vs a 1000 ceiling = 20% -> OK; bump opus to cross WARN.
    usage = {"weekly": {"claude-opus-4-8": 160}}  # 160 * 5 = 800 / 1000 = 80% -> WARN
    report = sq.run_quota_gate(budgets_path=budgets, usage=usage)
    assert report["enabled"] is True
    assert report["weekly_pct"] == 80.0
    assert report["weekly_band"] == "WARN"
    assert report["overall_band"] == "WARN"


def test_load_subscription_config(tmp_path):
    cfg = sq.load_subscription_config(_budgets(tmp_path, provider="anthropic"))
    assert cfg["provider"] == "anthropic"


def test_load_subscription_config_missing_file(tmp_path):
    assert sq.load_subscription_config(tmp_path / "nope.yml") == {}
