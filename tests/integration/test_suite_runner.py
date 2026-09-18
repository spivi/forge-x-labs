"""``run_suite`` — the harness's per-(family x scale x seed) orchestrator.

Covers the suite runner's acceptance criteria: the smoke spec produces 10 scenarios
with zero FAILs, the run tree matches design-doc §9, ``run_id`` is honored (never
generated), and determinism holds (same run_id + seeds -> identical manifests).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.cloudforge.io.loaders import load_yaml
from app.cloudforge.validate import tool_probe
from app.cloudforge.variation.models import RunManifest, VariationSpec
from app.cloudforge.variation.suite_runner import run_suite

_SMOKE_SPEC_PATH = Path("examples/variation/aws_smoke.yaml")


@pytest.fixture(autouse=True)
def _no_external_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force terraform/checkov/opa absent so the suite runner exercises the fail-soft
    WARN branch deterministically — never shelling out to a real ~700MB provider
    download per scenario (14 tests x 10 scenarios would exhaust the disk)."""
    monkeypatch.setattr(tool_probe, "detect_tool", lambda name: False)


def _smoke_spec() -> VariationSpec:
    return VariationSpec.model_validate(load_yaml(_SMOKE_SPEC_PATH))


def test_run_suite_smoke_produces_ten_scenarios(tmp_path: Path) -> None:
    result = run_suite(_smoke_spec(), tmp_path, run_id="smoke-1")

    assert len(result.manifest.entries) == 10


def test_run_suite_smoke_has_zero_failures(tmp_path: Path) -> None:
    result = run_suite(_smoke_spec(), tmp_path, run_id="smoke-2")

    fails = [e for e in result.manifest.entries if e.validation_status == "fail"]
    assert fails == [], fails


def test_run_suite_honors_run_id_parameter(tmp_path: Path) -> None:
    result = run_suite(_smoke_spec(), tmp_path, run_id="my-custom-run-id")

    assert result.manifest.run_id == "my-custom-run-id"
    assert (tmp_path / "my-custom-run-id").is_dir()


def test_run_suite_writes_manifest_diversity_and_per_scenario_graph(tmp_path: Path) -> None:
    run_suite(_smoke_spec(), tmp_path, run_id="smoke-3")
    run_dir = tmp_path / "smoke-3"

    assert (run_dir / "manifest.json").is_file()
    assert (run_dir / "diversity_report.json").is_file()
    manifest = RunManifest.model_validate(json.loads((run_dir / "manifest.json").read_text()))
    for entry in manifest.entries:
        scenario_dir = run_dir / "scenarios" / entry.scenario_id
        assert (scenario_dir / "graph.json").is_file()


def test_run_suite_output_tree_matches_design_doc_layout(tmp_path: Path) -> None:
    run_suite(_smoke_spec(), tmp_path, run_id="smoke-4")
    run_dir = tmp_path / "smoke-4"

    for name in (
        "variation_spec.yaml",
        "manifest.json",
        "summary.json",
        "diversity_report.json",
    ):
        assert (run_dir / name).is_file(), name
    assert (run_dir / "failures" / "raw").is_dir()
    assert (run_dir / "failures" / "minimized").is_dir()
    scenario_dirs = sorted((run_dir / "scenarios").iterdir())
    assert len(scenario_dirs) == 10
    one = scenario_dirs[0]
    assert (one / "scenario.yaml").is_file()
    assert (one / "graph.json").is_file()
    assert (one / "expected_findings.json").is_file()
    assert (one / "ground_truth_paths.json").is_file()
    assert (one / "terraform").is_dir()
    assert (one / "report.md").is_file()


def test_run_suite_is_deterministic_for_same_run_id_and_seeds(tmp_path: Path) -> None:
    out_a = tmp_path / "a"
    out_b = tmp_path / "b"
    result_a = run_suite(_smoke_spec(), out_a, run_id="det-run")
    result_b = run_suite(_smoke_spec(), out_b, run_id="det-run")

    dump_a = [e.model_dump(exclude={"gen_duration_sec"}) for e in result_a.manifest.entries]
    dump_b = [e.model_dump(exclude={"gen_duration_sec"}) for e in result_b.manifest.entries]
    assert dump_a == dump_b

    for entry in result_a.manifest.entries:
        graph_a = (out_a / "det-run" / "scenarios" / entry.scenario_id / "graph.json").read_text()
        graph_b = (out_b / "det-run" / "scenarios" / entry.scenario_id / "graph.json").read_text()
        assert graph_a == graph_b


def test_run_suite_aborts_after_max_failures(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """A spec whose ``max_failures_before_abort`` is exceeded stops the suite and
    preserves the partial run rather than continuing to burn through scenarios."""
    import app.cloudforge.variation.suite_runner as suite_runner_module

    spec = _smoke_spec()
    spec.constraints.max_failures_before_abort = 1

    def _always_fail(*args: object, **kwargs: object) -> object:
        raise RuntimeError("forced failure for abort test")

    monkeypatch.setattr(suite_runner_module, "_compose_bundle", _always_fail)

    result = run_suite(spec, tmp_path, run_id="abort-run")

    assert result.aborted is True
    assert len(result.manifest.entries) < 10
