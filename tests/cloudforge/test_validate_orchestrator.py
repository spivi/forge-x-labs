"""Fail-soft validation orchestration tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.cloudforge.io.paths import ScenarioPaths
from app.cloudforge.validate import tool_probe
from app.cloudforge.validate.orchestrator import run_validations
from app.cloudforge.validate.results import Status


@pytest.fixture(autouse=True)
def _no_external_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force every optional tool to look absent so tests are deterministic."""
    monkeypatch.setattr(tool_probe, "detect_tool", lambda name: False)


def test_validate_missing_tools_warns_not_fails(generated_scenario: Path) -> None:
    report = run_validations(generated_scenario)

    assert not report.has_failure


def test_validate_missing_checkov_emits_warn(generated_scenario: Path) -> None:
    report = run_validations(generated_scenario)

    checkov = next(o for o in report.outcomes if o.label == "checkov scan")
    assert checkov.status is Status.WARN


def test_validate_forbidden_perm_exits_nonzero(generated_scenario: Path) -> None:
    graph_path = generated_scenario / "graph.json"
    graph_path.write_text(
        graph_path.read_text(encoding="utf-8").replace("iam:PassRole", "iam:DeleteRole"),
        encoding="utf-8",
    )

    report = run_validations(generated_scenario)

    assert report.has_failure


def test_validate_clean_scenario_has_no_failure(generated_scenario: Path) -> None:
    report = run_validations(generated_scenario)

    risk = next(o for o in report.outcomes if o.label == "no forbidden permissions")
    assert risk.status is Status.PASS


def test_validate_no_scanner_output_scores_warn_not_scored(generated_scenario: Path) -> None:
    report = run_validations(generated_scenario)

    score = next(o for o in report.outcomes if o.label == "scanner score")
    assert score.status is Status.WARN
    assert "not scored" in score.detail


def test_validate_with_checkov_json_scores_and_writes_file(generated_scenario: Path) -> None:
    paths = ScenarioPaths.from_dir(generated_scenario)
    payload = {
        "results": {
            "failed_checks": [
                {"check_id": "CKV_AWS_60", "resource": "aws_iam_role.role_deploy"},
                {"check_id": "CKV_AWS_23", "resource": "aws_security_group.sg_web"},
            ],
            "passed_checks": [],
        }
    }
    paths.checkov_results.parent.mkdir(parents=True, exist_ok=True)
    paths.checkov_results.write_text(json.dumps(payload), encoding="utf-8")

    report = run_validations(generated_scenario)

    score = next(o for o in report.outcomes if o.label == "scanner score")
    assert score.status is Status.PASS
    assert paths.scanner_score.exists()
    on_disk = json.loads(paths.scanner_score.read_text(encoding="utf-8"))
    assert on_disk["scanner"] == "checkov"
