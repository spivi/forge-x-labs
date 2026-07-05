"""Tests for the ``public_data_exposure`` scenario family (FXL-26).

Mirrors the ci_cd_iam_chain coverage: generation works, the critical direct-exposure
path exists, forbidden-permission rejection still holds, and the report renders with
the local-only banner.
"""

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
from app.cloudforge.report.renderer import ReportRenderer
from app.cloudforge.validate.graph_risk import GraphRiskEngine
from app.cloudforge.validate.results import Status

_EXAMPLE = Path("examples/public_data_exposure.yaml")
_CRITICAL_PATH_ID = "path-critical-pde-01"


@pytest.fixture
def pde_spec() -> ScenarioSpec:
    return ScenarioSpec.model_validate(load_yaml(_EXAMPLE))


def _outcome(engine: GraphRiskEngine, label: str) -> Status:
    return next(o.status for o in engine.run() if o.label == label)


def test_generate_returns_graph(pde_spec: ScenarioSpec) -> None:
    bundle = TemplateGenerator().generate(pde_spec)

    assert len(bundle.graph.nodes) > 0
    assert len(bundle.graph.edges) > 0


def test_generate_respects_resource_budget(pde_spec: ScenarioSpec) -> None:
    bundle = TemplateGenerator().generate(pde_spec)

    assert len(bundle.graph.nodes) <= pde_spec.constraints.max_resources


def test_generate_includes_public_bucket_and_dataset(pde_spec: ScenarioSpec) -> None:
    bundle = TemplateGenerator().generate(pde_spec)

    bucket_ids = {n.id for n in bundle.graph.nodes if n.type is NodeType.S3_BUCKET}
    dataset_ids = {n.id for n in bundle.graph.nodes if n.type is NodeType.DATASET}
    assert "s3-public-data" in bucket_ids
    assert "s3-locked-backups" in bucket_ids
    assert len(dataset_ids) >= 1


def test_critical_direct_exposure_path_uses_exposure_edges(pde_spec: ScenarioSpec) -> None:
    bundle = TemplateGenerator().generate(pde_spec)

    edge_types = {e.type for e in bundle.graph.edges}
    assert EdgeType.EXPOSED_TO_INTERNET in edge_types
    assert EdgeType.STORES_SENSITIVE_DATA in edge_types

    path = next(p for p in bundle.ground_truth.paths if p.id == _CRITICAL_PATH_ID)
    assert path.severity == "critical"


def test_critical_path_reachable_returns_pass(pde_spec: ScenarioSpec) -> None:
    bundle = TemplateGenerator().generate(pde_spec)

    status = _outcome(GraphRiskEngine(bundle, pde_spec), "ground-truth path exists")

    assert status is Status.PASS


def test_findings_include_public_exposure_and_logging(pde_spec: ScenarioSpec) -> None:
    bundle = TemplateGenerator().generate(pde_spec)

    families = {f.family for f in bundle.findings.findings}
    assert FindingFamily.S3_PUBLIC_EXPOSURE in families
    assert FindingFamily.S3_LOGGING_MISSING in families
    assert FindingFamily.PUBLIC_LOOKING_BUCKET_WITH_COMPENSATING_CONTROL in families


def test_full_risk_engine_all_pass(pde_spec: ScenarioSpec) -> None:
    bundle = TemplateGenerator().generate(pde_spec)

    outcomes = GraphRiskEngine(bundle, pde_spec).run()

    assert all(o.status is Status.PASS for o in outcomes), [
        o.render() for o in outcomes if o.status is not Status.PASS
    ]


def test_forbidden_permission_rejection_holds(pde_spec: ScenarioSpec) -> None:
    from app.cloudforge.models.graph import GraphNode, NodeSecurity, NodeTags

    bundle = TemplateGenerator().generate(pde_spec)
    bundle.graph.nodes.append(
        GraphNode(
            id="pol-danger",
            type=NodeType.IAM_POLICY,
            name="DangerPolicy",
            tags=NodeTags(env="prod", owner="platform-team", app="data-lake"),
            security=NodeSecurity(criticality="high"),
            attributes={"actions": ["s3:DeleteBucket"]},
        )
    )

    status = _outcome(GraphRiskEngine(bundle, pde_spec), "no forbidden permissions")

    assert status is Status.FAIL


def test_report_renders_with_banner_and_critical_path(
    tmp_path: Path, pde_spec: ScenarioSpec
) -> None:
    bundle = TemplateGenerator().generate(pde_spec)
    out = tmp_path / "pde"
    ScenarioArtifacts(ScenarioPaths.from_dir(out)).write_all(pde_spec, bundle)

    report = ReportRenderer(out).render()

    assert constants.LOCAL_ONLY_BANNER in report
    assert _CRITICAL_PATH_ID in report
    assert "s3-public-data" in report
