"""Tests for scripts/estimator.py -- the cold-start estimate + model seeder.

Pure-logic functions are tested with injected seed/calibration/policy dicts so
no filesystem is touched. Loader tests use tmp_path.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

# scripts/ is not a package; load the module by path.
_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
_spec = importlib.util.spec_from_file_location("estimator", _SCRIPTS / "estimator.py")
estimator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(estimator)


@pytest.fixture
def seed() -> dict:
    return {
        "model_tiers": ["haiku", "sonnet", "opus"],
        "effort_floor": {"S": "haiku", "M": "sonnet", "L": "opus"},
        "default_floor": "sonnet",
        "base_minutes": {"tweak": 20, "fix": 45, "feature": 120, "default": 60},
        "type_model": {"docs": "haiku", "tweak": "haiku", "default": "sonnet"},
        "clamp_minutes": [5, 480],
    }


# --- effort parsing -------------------------------------------------------


def test_effort_from_labels_string():
    assert estimator.effort_from_labels("milestone:M0;effort:L;area:x") == "L"


def test_effort_from_labels_list():
    assert estimator.effort_from_labels(["type:feature", "effort:S"]) == "S"


def test_effort_from_labels_absent():
    assert estimator.effort_from_labels("type:feature") is None


def test_effort_from_labels_xl():
    assert estimator.effort_from_labels("milestone:M0;effort:XL;area:x") == "XL"


def test_dim_from_labels_open_vocab():
    assert estimator.dim_from_labels("effort:L;area:api;risk:high", "area:") == "api"
    assert estimator.dim_from_labels("effort:L;risk:high", "risk:") == "high"


def test_dim_from_labels_absent():
    assert estimator.dim_from_labels("type:feature", "area:") is None


# --- calibration factor ---------------------------------------------------


def test_calibration_factor_defaults_to_one_when_empty():
    assert estimator.calibration_factor({}, "feature", "M") == 1.0


def test_calibration_factor_prefers_type_over_effort():
    cal = {
        "factors": {
            "type:feature": {"factor": 0.5},
            "label:effort:M": {"factor": 2.0},
        }
    }
    assert estimator.calibration_factor(cal, "feature", "M") == 0.5


def test_calibration_factor_falls_back_to_effort():
    cal = {"factors": {"label:effort:M": {"factor": 1.5}}}
    assert estimator.calibration_factor(cal, "feature", "M") == 1.5


# --- estimate minutes -----------------------------------------------------


def test_estimate_minutes_uses_base_when_no_calibration(seed):
    assert estimator.estimate_minutes("feature", "M", seed, {}) == 120


def test_estimate_minutes_applies_calibration_factor(seed):
    cal = {"factors": {"type:feature": {"factor": 0.5}}}
    assert estimator.estimate_minutes("feature", "M", seed, cal) == 60


def test_estimate_minutes_unknown_type_uses_default(seed):
    assert estimator.estimate_minutes("mystery", "M", seed, {}) == 60


def test_estimate_minutes_clamped_low(seed):
    cal = {"factors": {"type:tweak": {"factor": 0.01}}}  # 20*0.01 = 0.2 -> clamp 5
    assert estimator.estimate_minutes("tweak", "S", seed, cal) == 5


def test_estimate_minutes_clamped_high(seed):
    cal = {"factors": {"type:feature": {"factor": 10.0}}}  # 1200 -> clamp 480
    assert estimator.estimate_minutes("feature", "L", seed, cal) == 480


# --- model routing (cheapest-sufficient) ----------------------------------


def test_recommend_model_uses_effort_floor(seed):
    # M effort floors to sonnet, no policy override
    assert estimator.recommend_model("feature", "M", "effort:M", seed, {}) == "sonnet"


def test_recommend_model_s_effort_floors_to_haiku(seed):
    assert estimator.recommend_model("tweak", "S", "effort:S", seed, {}) == "haiku"


def test_recommend_model_never_drops_below_floor(seed):
    # Policy says haiku is fine, but effort L floors to opus -> floor wins.
    policy = {"learned": {"type:feature": {"recommended_model": "haiku"}}}
    assert estimator.recommend_model("feature", "L", "effort:L", seed, policy) == "opus"


def test_recommend_model_uptiers_when_policy_underpowered(seed):
    # S effort floors to haiku, but policy learned this type needs opus.
    policy = {"learned": {"type:feature": {"recommended_model": "opus"}}}
    assert estimator.recommend_model("feature", "S", "effort:S", seed, policy) == "opus"


def test_recommend_model_no_effort_uses_default_floor(seed):
    assert estimator.recommend_model("feature", None, "type:feature", seed, {}) == "sonnet"


def test_recommend_model_consults_risk_policy(seed):
    # No type/effort policy, but the learned risk:high policy up-tiers to opus.
    policy = {"learned": {"label:risk:high": {"recommended_model": "opus"}}}
    assert estimator.recommend_model("tweak", "S", "effort:S;risk:high", seed, policy) == "opus"


def test_recommend_model_external_executor_passes_through_seed(seed):
    # An external executor configured via type_model bypasses the tier floor
    # (external:* is off the haiku/sonnet/opus ladder, not floor-clamped).
    seed2 = {**seed, "type_model": {**seed["type_model"], "spike": "external:codex"}}
    assert estimator.recommend_model("spike", "L", "effort:L", seed2, {}) == "external:codex"


def test_recommend_model_external_executor_from_policy(seed):
    policy = {"learned": {"type:spike": {"recommended_model": "external:codex"}}}
    assert estimator.recommend_model("spike", "S", "effort:S", seed, policy) == "external:codex"


def test_recommend_model_type_still_wins_over_risk(seed):
    # type policy takes precedence over a conflicting risk policy.
    policy = {
        "learned": {
            "type:feature": {"recommended_model": "sonnet"},
            "label:risk:high": {"recommended_model": "opus"},
        }
    }
    assert (
        estimator.recommend_model("feature", "M", "effort:M;risk:high", seed, policy) == "sonnet"
    )


# --- plan_ticket aggregate ------------------------------------------------


def test_plan_ticket_returns_both(seed):
    out = estimator.plan_ticket("feature", "M", "effort:M", seed, {}, {})
    assert out == {"estimate_minutes": 120, "recommended_model": "sonnet"}


# --- loaders --------------------------------------------------------------


def test_load_calibration_missing_returns_empty(tmp_path):
    assert estimator.load_calibration(tmp_path / "nope.json") == {}


def test_load_calibration_reads_file(tmp_path):
    p = tmp_path / "calibration.json"
    p.write_text(json.dumps({"factors": {"type:fix": {"factor": 0.7}}}))
    assert estimator.load_calibration(p)["factors"]["type:fix"]["factor"] == 0.7


def test_load_seed_reads_yaml(tmp_path):
    p = tmp_path / "base-estimates.yml"
    p.write_text("base_minutes:\n  feature: 99\n  default: 60\n")
    assert estimator.load_seed(p)["base_minutes"]["feature"] == 99


def test_load_taxonomy_missing_returns_empty(tmp_path):
    assert estimator.load_taxonomy(tmp_path / "nope.yml") == {}


def test_load_taxonomy_reads_yaml(tmp_path):
    p = tmp_path / "taxonomy.yml"
    p.write_text("dimensions:\n  effort:\n    allowed: [S, M, L, XL]\n")
    assert estimator.load_taxonomy(p)["dimensions"]["effort"]["allowed"] == ["S", "M", "L", "XL"]
