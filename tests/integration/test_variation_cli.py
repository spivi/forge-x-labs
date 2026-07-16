"""CLI tests for the ``cloudforge variation`` command group (FXL-VAR-1f).

Covers the ACs: ``run`` exits 0 and writes a manifest; ``summarize`` exits 0; every
handler is wrapped in ``_CLI_ERRORS`` so bad input surfaces as a clean ``error:`` + exit 1
(no raw traceback). Tests force terraform/checkov/opa absent (the established
``tests/integration`` pattern) so they are hermetic + fast (no ~700MB provider download).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from app.cli import app
from app.cloudforge.validate import tool_probe

runner = CliRunner()

_SMOKE = "examples/variation/aws_smoke.yaml"


@pytest.fixture(autouse=True)
def _no_external_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tool_probe, "detect_tool", lambda name: False)


def _run(tmp_path: Path, run_id: str = "cli-run") -> Path:
    # --out IS the run directory (the verifier checks <out>/manifest.json directly).
    out = tmp_path / run_id
    r = runner.invoke(app, ["variation", "run", _SMOKE, "--out", str(out), "--run-id", run_id])
    assert r.exit_code == 0, r.output
    return out


def test_run_writes_manifest_directly_under_out(tmp_path: Path) -> None:
    run_dir = _run(tmp_path)
    # The manifest lands directly under --out (matches the ticket verifier).
    assert (run_dir / "manifest.json").is_file()
    assert (run_dir / "diversity_report.json").is_file()
    assert (run_dir / "summary.json").is_file()


def test_run_honors_run_id_label(tmp_path: Path) -> None:
    import json

    run_dir = _run(tmp_path, run_id="my-id")
    manifest = json.loads((run_dir / "manifest.json").read_text())
    summary = json.loads((run_dir / "summary.json").read_text())
    assert manifest["run_id"] == "my-id"
    assert summary["run_id"] == "my-id"


def test_summarize_exits_zero(tmp_path: Path) -> None:
    run_dir = _run(tmp_path)
    r = runner.invoke(app, ["variation", "summarize", str(run_dir)])
    assert r.exit_code == 0, r.output
    assert "scenarios" in r.output


def test_replay_ok_for_a_real_scenario(tmp_path: Path) -> None:
    run_dir = _run(tmp_path)
    # Any scenario id from the deterministic sweep (family-scale-seed).
    scenario_id = "ci_cd_iam_chain-tiny-seed0"
    r = runner.invoke(app, ["variation", "replay", str(run_dir), "--scenario-id", scenario_id])
    assert r.exit_code == 0, r.output
    assert "replay ok" in r.output


def test_minimize_failure_exits_zero(tmp_path: Path) -> None:
    run_dir = _run(tmp_path)
    scenario_id = "ci_cd_iam_chain-tiny-seed0"
    r = runner.invoke(
        app, ["variation", "minimize-failure", str(run_dir), "--scenario-id", scenario_id]
    )
    assert r.exit_code == 0, r.output
    assert (run_dir / "failures" / "minimized" / scenario_id).is_dir()


def test_run_bad_spec_is_clean_error_not_traceback(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "families: []\nseed_count: 0\n", encoding="utf-8"
    )  # fails VariationSpec validation
    r = runner.invoke(
        app, ["variation", "run", str(bad), "--out", str(tmp_path / "o"), "--run-id", "x"]
    )
    assert r.exit_code == 1
    assert "error:" in r.output
    assert "Traceback" not in r.output


def test_summarize_missing_dir_is_clean_error(tmp_path: Path) -> None:
    r = runner.invoke(app, ["variation", "summarize", str(tmp_path / "nope")])
    assert r.exit_code == 1
    assert "error:" in r.output
    assert "Traceback" not in r.output


def test_replay_unknown_scenario_is_clean_error(tmp_path: Path) -> None:
    run_dir = _run(tmp_path)
    r = runner.invoke(app, ["variation", "replay", str(run_dir), "--scenario-id", "ghost"])
    assert r.exit_code == 1
    assert "error:" in r.output
    assert "Traceback" not in r.output
