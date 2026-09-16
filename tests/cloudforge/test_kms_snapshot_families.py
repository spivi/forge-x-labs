"""Template-engine tests for kms_key_overbroad and public_ebs_snapshot."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.cloudforge.generate.template_generator import TemplateGenerator
from app.cloudforge.io.loaders import load_yaml
from app.cloudforge.models.findings import FindingFamily
from app.cloudforge.models.graph import NodeType
from app.cloudforge.models.scenario import ScenarioSpec
from app.cloudforge.validate.graph_risk import GraphRiskEngine
from app.cloudforge.validate.results import Status


@pytest.mark.parametrize(
    ("example", "node_type", "family"),
    [
        (
            "examples/kms_key_overbroad.yaml",
            NodeType.KMS_KEY,
            FindingFamily.KMS_KEY_POLICY_OVERBROAD,
        ),
        (
            "examples/public_ebs_snapshot.yaml",
            NodeType.EBS_SNAPSHOT,
            FindingFamily.EBS_SNAPSHOT_PUBLIC,
        ),
    ],
)
def test_family_generates_and_risk_engine_passes(
    example: str, node_type: NodeType, family: FindingFamily
) -> None:
    spec = ScenarioSpec.model_validate(load_yaml(Path(example)))
    bundle = TemplateGenerator().generate(spec)
    assert any(n.type is node_type for n in bundle.graph.nodes)
    assert family in {f.family for f in bundle.findings.findings}
    fails = [o for o in GraphRiskEngine(bundle, spec).run() if o.status is Status.FAIL]
    assert fails == []
