"""Replay + failure-capture/minimize integration tests.

- ``replay`` proves a manifest entry's key artifacts are byte-reproducible.
- ``capture_failure`` preserves the raw scenario tree + logs + exception (a COPY,
  never a move); ``minimize`` shrinks to a smaller reproducer and NEVER deletes or
  mutates the raw originals.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.cloudforge.io.loaders import load_yaml
from app.cloudforge.models.scenario import ScenarioSpec
from app.cloudforge.validate import tool_probe
from app.cloudforge.variation.minimize import capture_failure, minimize
from app.cloudforge.variation.models import VariationSpec
from app.cloudforge.variation.replay import replay
from app.cloudforge.variation.suite_runner import run_suite

_SMOKE_SPEC_PATH = Path("examples/variation/aws_smoke.yaml")
_CI_CD_SPEC_PATH = Path("examples/ci_cd_iam_chain.yaml")


@pytest.fixture(autouse=True)
def _no_external_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force terraform/checkov/opa absent — hermetic, fast, disk-safe (see
    test_suite_runner for the rationale)."""
    monkeypatch.setattr(tool_probe, "detect_tool", lambda name: False)


def _smoke_spec() -> VariationSpec:
    return VariationSpec.model_validate(load_yaml(_SMOKE_SPEC_PATH))


def _scenario_spec(scale: str = "small") -> ScenarioSpec:
    data = load_yaml(_CI_CD_SPEC_PATH)
    data["scale_profile"] = scale
    data.setdefault("variation_axes", {})
    return ScenarioSpec.model_validate(data)


def test_replay_true_for_a_real_run(tmp_path: Path) -> None:
    """A freshly-composed scenario replays byte-identically to its manifest artifacts."""
    result = run_suite(_smoke_spec(), tmp_path, run_id="replay-run")
    scenario_id = result.manifest.entries[0].scenario_id

    assert replay(tmp_path / "replay-run", scenario_id) is True


def test_replay_true_for_every_scenario(tmp_path: Path) -> None:
    """Determinism holds across the whole smoke sweep, not one lucky scenario."""
    result = run_suite(_smoke_spec(), tmp_path, run_id="replay-all")
    run_dir = tmp_path / "replay-all"

    for entry in result.manifest.entries:
        assert replay(run_dir, entry.scenario_id) is True, entry.scenario_id


def test_replay_false_when_artifact_tampered(tmp_path: Path) -> None:
    """Replay must actually detect a byte-diff, not just always return True."""
    result = run_suite(_smoke_spec(), tmp_path, run_id="replay-tamper")
    run_dir = tmp_path / "replay-tamper"
    entry = result.manifest.entries[0]
    graph = run_dir / entry.artifact_dir / "graph.json"  # artifact_dir is relative to run_dir
    graph.write_text(graph.read_text() + "\n{}", encoding="utf-8")

    assert replay(run_dir, entry.scenario_id) is False


def _run_dir_with_raw_scenario(tmp_path: Path) -> tuple[Path, str, Path]:
    """A run dir whose one scenario has real artifacts written, ready to fail-capture."""
    result = run_suite(_smoke_spec(), tmp_path, run_id="cap-run")
    run_dir = tmp_path / "cap-run"
    entry = result.manifest.entries[0]
    return run_dir, entry.scenario_id, run_dir / entry.artifact_dir


def test_capture_failure_preserves_raw_artifacts_and_logs(tmp_path: Path) -> None:
    run_dir, scenario_id, scenario_dir = _run_dir_with_raw_scenario(tmp_path)

    failure_id = capture_failure(
        run_dir, scenario_id, scenario_dir, ValueError("boom: something went wrong")
    )

    raw = run_dir / "failures" / "raw" / failure_id
    assert failure_id == scenario_id
    assert (raw / "graph.json").is_file()  # raw scenario artifacts copied
    log = (raw / "failure.log").read_text()
    assert "boom: something went wrong" in log  # exception message
    assert "ValueError" in log  # traceback
    # The original scenario tree is untouched (copy, not move).
    assert (scenario_dir / "graph.json").is_file()


def test_capture_failure_when_scenario_dir_missing(tmp_path: Path) -> None:
    """A compose error before any artifact is written still captures a log dir."""
    run_dir = tmp_path / "no-artifacts"
    (run_dir / "failures" / "raw").mkdir(parents=True)

    failure_id = capture_failure(
        run_dir, "ghost-scenario", run_dir / "scenarios" / "ghost", RuntimeError("early boom")
    )

    raw = run_dir / "failures" / "raw" / failure_id
    assert (raw / "failure.log").is_file()
    assert "early boom" in (raw / "failure.log").read_text()


def test_minimize_writes_reproducer_without_deleting_raw(tmp_path: Path) -> None:
    """minimize() never mutates or deletes the raw originals (hard AC)."""
    run_dir, scenario_id, scenario_dir = _run_dir_with_raw_scenario(tmp_path)
    capture_failure(run_dir, scenario_id, scenario_dir, RuntimeError("boom"))
    raw = run_dir / "failures" / "raw" / scenario_id
    raw_graph_before = (raw / "graph.json").read_bytes()

    minimized_dir = minimize(run_dir, scenario_id, _scenario_spec("medium"), seed=1)

    assert minimized_dir == run_dir / "failures" / "minimized" / scenario_id
    assert (minimized_dir / "graph.json").is_file()
    # Raw originals are byte-for-byte untouched.
    assert (raw / "graph.json").read_bytes() == raw_graph_before
    assert (raw / "failure.log").is_file()
