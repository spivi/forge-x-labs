"""Integrity regression net: every composed scenario passes the full validator
suite across families x seeds, proving ground-truth agreement holds under
fragment composition.

This is the ground-truth-preserving core of FXL-VAR-1c. The assertion must never
be weakened; any FAIL is a real integrity bug to fix at the fragment/composer
source.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.cloudforge.generate.composer import GraphComposer
from app.cloudforge.io.loaders import load_yaml
from app.cloudforge.io.paths import ScenarioPaths
from app.cloudforge.models.scenario import ScenarioSpec
from app.cloudforge.pipeline.artifacts import ScenarioArtifacts
from app.cloudforge.validate import tool_probe
from app.cloudforge.validate.orchestrator import run_validations
from app.cloudforge.validate.results import Status

_SEEDS = [0, 1, 2, 17, 99]
_FAMILIES = ["ci_cd_iam_chain", "public_data_exposure", "cross_account_trust"]


@pytest.fixture(autouse=True)
def _no_external_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tool_probe, "detect_tool", lambda name: False)


def _spec(family: str) -> ScenarioSpec:
    data = load_yaml(Path(f"examples/{family}.yaml"))
    data["scale_profile"] = "small"
    return ScenarioSpec.model_validate(data)


@pytest.mark.parametrize("family", _FAMILIES)
@pytest.mark.parametrize("seed", _SEEDS)
def test_composed_scenarios_have_no_validation_failure(
    tmp_path: Path, family: str, seed: int
) -> None:
    spec = _spec(family)
    bundle = GraphComposer(spec, seed=seed).generate()
    out = tmp_path / f"{family}_{seed}"
    ScenarioArtifacts(ScenarioPaths.from_dir(out)).write_all(spec, bundle)
    report = run_validations(out)
    fails = [o.render() for o in report.outcomes if o.status is Status.FAIL]
    assert fails == [], f"FAILs for {family}/{seed}: {fails}"


@pytest.mark.parametrize("family", _FAMILIES)
@pytest.mark.parametrize("seed", _SEEDS)
def test_composed_scenarios_are_deterministic(family: str, seed: int) -> None:
    a = GraphComposer(_spec(family), seed=seed).generate()
    b = GraphComposer(_spec(family), seed=seed).generate()
    assert a.graph.model_dump(by_alias=True) == b.graph.model_dump(by_alias=True)
    assert a.findings.model_dump() == b.findings.model_dump()
    assert a.ground_truth.model_dump() == b.ground_truth.model_dump()
