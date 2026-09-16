"""Unit tests for the diversity acceptance gate (FXL-VAR-1g).

``evaluate_gate`` consumes the live ``diversity_report.json`` shape written by
the suite runner (suite-level metrics, percents on 0–100, ``unsupported_axes``
per family). A rich report passes; a shallow one fails and names the dimension.
"""

from __future__ import annotations

from pathlib import Path

from app.cloudforge.io.loaders import load_yaml
from app.cloudforge.variation.gate import GateThresholds, evaluate_gate
from app.cloudforge.variation.models import VariationSpec


def _report(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "total_scenarios": 10,
        "unique_graph_shapes": 6,
        "critical_path_lengths": [2, 3, 4, 5],
        "scanner_score_profiles": ["not_scored"],
        "pct_with_decoys": 25.0,
        "pct_with_false_positives": 15.0,
        "pct_with_compensating_controls": 30.0,
        "families": ["ci_cd_iam_chain"],
        "unsupported_axes": {},
    }
    base.update(overrides)
    return base


def test_rich_report_passes() -> None:
    res = evaluate_gate(_report(), GateThresholds())
    assert res.passed is True
    assert res.failures == []


def test_shallow_report_fails_loudly_on_shapes() -> None:
    res = evaluate_gate(_report(unique_graph_shapes=1), GateThresholds())
    assert res.passed is False
    assert any("unique_graph_shapes" in item for item in res.failures)


def test_zero_decoys_fails_naming_the_dimension() -> None:
    res = evaluate_gate(_report(pct_with_decoys=0.0), GateThresholds())
    assert res.passed is False
    assert any("pct_with_decoys" in item for item in res.failures)


def test_missing_checkov_is_warn_not_fail() -> None:
    res = evaluate_gate(_report(scanner_score_profiles=["not_scored"]), GateThresholds())
    assert all("scanner" not in item for item in res.failures)
    assert any("scanner_score_profiles" in item for item in res.warnings)


def test_too_few_scanner_profiles_fails_when_scored() -> None:
    res = evaluate_gate(
        _report(scanner_score_profiles=["profile-a", "profile-b"]), GateThresholds()
    )
    assert res.passed is False
    assert any("scanner_score_profiles" in item for item in res.failures)


def test_unsupported_path_length_is_not_counted() -> None:
    res = evaluate_gate(
        _report(
            critical_path_lengths=[3],
            unsupported_axes={"public_data_exposure": ["path_length"]},
            families=["public_data_exposure"],
        ),
        GateThresholds(),
    )
    assert all("critical_path_lengths" not in item for item in res.failures)
    assert "path_length" in res.unsupported


def test_too_few_path_lengths_fails_when_supported() -> None:
    res = evaluate_gate(_report(critical_path_lengths=[3]), GateThresholds())
    assert res.passed is False
    assert any("critical_path_lengths" in item for item in res.failures)


def test_ci_and_large_example_specs_load() -> None:
    for name in ("aws_ci.yaml", "aws_large.yaml"):
        spec = VariationSpec.model_validate(load_yaml(Path("examples/variation") / name))
        assert spec.families == ["ci_cd_iam_chain", "public_data_exposure"]
        assert spec.constraints.no_apply is True
