"""CLI wiring for ``variation run --gate``.

A one-seed suite is structurally shallow, so ``--gate`` must exit 1 and print
``cosmetic variation only``. External tools are forced absent (hermetic).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from app.cli import app
from app.cloudforge.validate import tool_probe

runner = CliRunner()

_SHALLOW = """
families:
  - ci_cd_iam_chain
seed_start: 0
seed_count: 1
scale_profiles:
  - tiny
variation_axes:
  decoy: ["0"]
  fp: ["0"]
  ctrl: ["0"]
constraints:
  no_apply: true
  no_credentials: true
  max_failures_before_abort: 25
validation_profile:
  run_validate: true
  run_report: true
  run_terraform_validate: if_available
  run_checkov: if_available
  run_opa: if_available
"""


@pytest.fixture(autouse=True)
def _no_external_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tool_probe, "detect_tool", lambda name: False)


def test_gate_flag_fails_shallow_suite(tmp_path: Path) -> None:
    spec = tmp_path / "shallow.yaml"
    spec.write_text(_SHALLOW)
    out = tmp_path / "run"
    result = runner.invoke(
        app,
        ["variation", "run", str(spec), "--out", str(out), "--run-id", "shallow", "--gate"],
    )
    assert result.exit_code == 1, result.output
    assert "cosmetic variation only" in result.output
    assert (out / "diversity_report.json").is_file()


def test_run_without_gate_still_exits_zero_on_shallow_suite(tmp_path: Path) -> None:
    spec = tmp_path / "shallow.yaml"
    spec.write_text(_SHALLOW)
    out = tmp_path / "run"
    result = runner.invoke(
        app,
        ["variation", "run", str(spec), "--out", str(out), "--run-id", "shallow"],
    )
    assert result.exit_code == 0, result.output
