"""Tests for the ``cross_account_trust`` family."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.cloudforge import constants
from app.cloudforge.generate.template_generator import TemplateGenerator
from app.cloudforge.io.loaders import load_yaml
from app.cloudforge.io.paths import ScenarioPaths
from app.cloudforge.models.findings import FindingFamily
from app.cloudforge.models.graph import EdgeType, NodeType
from app.cloudforge.models.scenario import ScenarioSpec
from app.cloudforge.pipeline.artifacts import ScenarioArtifacts
from app.cloudforge.validate.graph_risk import GraphRiskEngine
from app.cloudforge.validate.results import Status

_EXAMPLE = Path("examples/cross_account_trust.yaml")
_CRITICAL_PATH_ID = "path-critical-xacct-01"


@pytest.fixture
def spec() -> ScenarioSpec:
    return ScenarioSpec.model_validate(load_yaml(_EXAMPLE))


def _outcome(engine: GraphRiskEngine, label: str) -> Status:
    return next(o.status for o in engine.run() if o.label == label)


def test_generate_returns_graph(spec: ScenarioSpec) -> None:
    bundle = TemplateGenerator().generate(spec)
    assert bundle.graph.nodes and bundle.graph.edges


def test_includes_external_account_and_shared_role(spec: ScenarioSpec) -> None:
    bundle = TemplateGenerator().generate(spec)
    accounts = {n.id: n for n in bundle.graph.nodes if n.type is NodeType.ACCOUNT}
    assert "acct-external" in accounts
    assert accounts["acct-external"].attributes.get("account_id") == (
        constants.EXTERNAL_DUMMY_ACCOUNT_ID
    )
    roles = {n.id for n in bundle.graph.nodes if n.type is NodeType.IAM_ROLE}
    assert "role-shared" in roles


def test_critical_path_is_cross_account_assume(spec: ScenarioSpec) -> None:
    bundle = TemplateGenerator().generate(spec)
    assert EdgeType.ASSUMES in {e.type for e in bundle.graph.edges}
    path = next(p for p in bundle.ground_truth.paths if p.id == _CRITICAL_PATH_ID)
    assert path.severity == "critical"
    assert path.nodes[0] == "acct-external"


def test_findings_include_cross_account_trust(spec: ScenarioSpec) -> None:
    bundle = TemplateGenerator().generate(spec)
    families = {f.family for f in bundle.findings.findings}
    assert FindingFamily.IAM_CROSS_ACCOUNT_TRUST in families
    assert FindingFamily.S3_LOGGING_MISSING in families


def test_full_risk_engine_all_pass(spec: ScenarioSpec) -> None:
    bundle = TemplateGenerator().generate(spec)
    fails = [o for o in GraphRiskEngine(bundle, spec).run() if o.status is Status.FAIL]
    assert fails == []


def test_emits_terraform(tmp_path: Path, spec: ScenarioSpec) -> None:
    bundle = TemplateGenerator().generate(spec)
    out = tmp_path / "xacct"
    ScenarioArtifacts(ScenarioPaths.from_dir(out)).write_all(spec, bundle)
    assert (out / "terraform" / "iam.tf").read_text()
    assert (out / "terraform" / "s3.tf").read_text()
