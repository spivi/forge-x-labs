"""Integrity regression net: every composed scenario passes the full validator
suite across families x seeds, proving ground-truth agreement holds under
fragment composition.

This is the ground-truth-preserving core of the graph composer. The assertion must never
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
_FAMILIES = [
    "ci_cd_iam_chain",
    "public_data_exposure",
    "cross_account_trust",
    "kms_key_overbroad",
    "public_ebs_snapshot",
    "iam_privesc_policy_version",
    "ec2_imds_credential_exfil",
    "lambda_public_function_url",
    "secretsmanager_policy_overbroad",
    "public_rds_instance",
    "ecr_repository_public_read",
    "sqs_queue_overbroad_policy",
    "k8s_pod_irsa_exfil",
    "azure_imds_keyvault_harvest",
    "gcp_workload_identity_federation",
]


@pytest.fixture(autouse=True)
def _no_external_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tool_probe, "detect_tool", lambda name: False)


def _spec(family: str, difficulty: str | None = None) -> ScenarioSpec:
    data = load_yaml(Path(f"examples/{family}.yaml"))
    data["scale_profile"] = "small"
    if difficulty is not None:
        data["difficulty"] = difficulty
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
@pytest.mark.parametrize("seed", [0, 17])
@pytest.mark.parametrize("difficulty", ["easy", "medium", "hard"])
def test_every_difficulty_validates(
    tmp_path: Path, family: str, seed: int, difficulty: str
) -> None:
    """Difficulty shapes the path (hops, branches, lookalikes, a second route);
    every shape must still pass the full validator suite."""
    spec = _spec(family, difficulty)
    bundle = GraphComposer(spec, seed=seed).generate()
    out = tmp_path / f"{family}_{difficulty}_{seed}"
    ScenarioArtifacts(ScenarioPaths.from_dir(out)).write_all(spec, bundle)
    report = run_validations(out)
    fails = [o.render() for o in report.outcomes if o.status is Status.FAIL]
    assert fails == [], f"FAILs for {family}/{difficulty}/{seed}: {fails}"


@pytest.mark.parametrize("family", _FAMILIES)
@pytest.mark.parametrize("seed", _SEEDS)
def test_composed_scenarios_are_deterministic(family: str, seed: int) -> None:
    a = GraphComposer(_spec(family), seed=seed).generate()
    b = GraphComposer(_spec(family), seed=seed).generate()
    assert a.graph.model_dump(by_alias=True) == b.graph.model_dump(by_alias=True)
    assert a.findings.model_dump() == b.findings.model_dump()
    assert a.ground_truth.model_dump() == b.ground_truth.model_dump()
