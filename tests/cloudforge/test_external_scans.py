"""External-scanner runner tests: fail-soft classification of tool outcomes."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.cloudforge.io.paths import ScenarioPaths
from app.cloudforge.validate import external_scans, tool_probe
from app.cloudforge.validate.results import Status
from app.cloudforge.validate.tool_probe import ToolRun


def _paths(tmp_path: Path) -> ScenarioPaths:
    return ScenarioPaths.from_dir(tmp_path)


def test_terraform_present_and_valid_returns_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tool_probe, "detect_tool", lambda name: True)
    monkeypatch.setattr(external_scans.tool_probe, "run_tool", lambda *a, **k: ToolRun(0, "", ""))

    outcome = external_scans.run_terraform(_paths(tmp_path))

    assert outcome.status is Status.PASS


def test_terraform_network_error_classified_as_warn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tool_probe, "detect_tool", lambda name: True)
    monkeypatch.setattr(
        external_scans.tool_probe,
        "run_tool",
        lambda *a, **k: ToolRun(1, "", "failed to download provider from registry"),
    )

    outcome = external_scans.run_terraform(_paths(tmp_path))

    assert outcome.status is Status.WARN


def test_terraform_config_error_classified_as_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tool_probe, "detect_tool", lambda name: True)
    # init OK, validate reports a real config error (no network hint).
    runs = iter([ToolRun(0, "", ""), ToolRun(1, "", "Error: Invalid resource type")])
    monkeypatch.setattr(external_scans.tool_probe, "run_tool", lambda *a, **k: next(runs))

    outcome = external_scans.run_terraform(_paths(tmp_path))

    assert outcome.status is Status.FAIL


def test_opa_denial_returns_fail(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tool_probe, "detect_tool", lambda name: True)
    denial = '{"result":[{"expressions":[{"value":["forbidden permission"]}]}]}'
    monkeypatch.setattr(
        external_scans.tool_probe, "run_tool", lambda *a, **k: ToolRun(0, denial, "")
    )

    outcome = external_scans.run_opa(_paths(tmp_path), "policies/scenario.rego")

    assert outcome.status is Status.FAIL


def test_opa_no_denial_returns_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tool_probe, "detect_tool", lambda name: True)
    clean = '{"result":[{"expressions":[{"value":[]}]}]}'
    monkeypatch.setattr(
        external_scans.tool_probe, "run_tool", lambda *a, **k: ToolRun(0, clean, "")
    )

    outcome = external_scans.run_opa(_paths(tmp_path), "policies/scenario.rego")

    assert outcome.status is Status.PASS
