"""Fail-soft validation orchestration tests."""

from __future__ import annotations

from pathlib import Path

import pytest

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
