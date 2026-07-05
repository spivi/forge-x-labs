"""End-to-end CLI tests via Typer's CliRunner."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from app.cli import app
from app.cloudforge.validate import tool_probe

runner = CliRunner()


@pytest.fixture(autouse=True)
def _no_external_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tool_probe, "detect_tool", lambda name: False)


def test_generate_then_validate_then_report_succeeds(tmp_path: Path) -> None:
    out = tmp_path / "scenario_001"

    gen = runner.invoke(app, ["generate", "examples/ci_cd_iam_chain.yaml", "--out", str(out)])
    val = runner.invoke(app, ["validate", str(out)])
    rep = runner.invoke(app, ["report", str(out)])

    assert gen.exit_code == 0
    assert val.exit_code == 0
    assert rep.exit_code == 0


def test_generate_missing_input_exits_error(tmp_path: Path) -> None:
    result = runner.invoke(app, ["generate", "does-not-exist.yaml", "--out", str(tmp_path / "s")])

    assert result.exit_code == 1


def test_generated_tree_has_expected_files(tmp_path: Path) -> None:
    out = tmp_path / "scenario_001"

    runner.invoke(app, ["generate", "examples/ci_cd_iam_chain.yaml", "--out", str(out)])

    assert (out / "graph.json").exists()
    assert (out / "terraform" / "iam.tf").exists()


def test_version_command_prints_version() -> None:
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert result.stdout.strip()
