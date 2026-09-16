"""Template, risk-engine, emitter, and composer tests for 7 new scenario families."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.cloudforge import constants
from app.cloudforge.generate.composer import GraphComposer
from app.cloudforge.generate.template_generator import TemplateGenerator
from app.cloudforge.io.loaders import load_yaml
from app.cloudforge.models.findings import FindingFamily
from app.cloudforge.models.graph import NodeType
from app.cloudforge.models.scenario import ScenarioSpec
from app.cloudforge.pipeline.terraform_emitter import TerraformEmitter
from app.cloudforge.validate.graph_risk import GraphRiskEngine
from app.cloudforge.validate.results import Status

_FAMILIES = [
    (
        "iam_privesc_policy_version",
        NodeType.IAM_POLICY,
        FindingFamily.IAM_PRIVESC_POLICY_VERSION,
    ),
    (
        "ec2_imds_credential_exfil",
        NodeType.EC2_INSTANCE,
        FindingFamily.EC2_IMDSV1_ENABLED,
    ),
    (
        "lambda_public_function_url",
        NodeType.LAMBDA_FUNCTION,
        FindingFamily.LAMBDA_FUNCTION_URL_UNAUTHENTICATED,
    ),
    (
        "secretsmanager_policy_overbroad",
        NodeType.SECRETS_MANAGER_SECRET,
        FindingFamily.SECRETSMANAGER_POLICY_OVERBROAD,
    ),
    (
        "public_rds_instance",
        NodeType.RDS_INSTANCE,
        FindingFamily.RDS_INSTANCE_PUBLIC,
    ),
    (
        "ecr_repository_public_read",
        NodeType.ECR_REPOSITORY,
        FindingFamily.ECR_REPOSITORY_PUBLIC_READ,
    ),
    (
        "sqs_queue_overbroad_policy",
        NodeType.SQS_QUEUE,
        FindingFamily.SQS_QUEUE_POLICY_OVERBROAD,
    ),
]


def _spec(name: str) -> ScenarioSpec:
    return ScenarioSpec.model_validate(load_yaml(Path(f"examples/{name}.yaml")))


@pytest.mark.parametrize(("name", "node_type", "family"), _FAMILIES)
def test_new_family_template_and_risk_engine(
    name: str, node_type: NodeType, family: FindingFamily
) -> None:
    spec = _spec(name)
    bundle = TemplateGenerator().generate(spec)
    assert any(n.type is node_type for n in bundle.graph.nodes)
    assert family in {f.family for f in bundle.findings.findings}
    fails = [o for o in GraphRiskEngine(bundle, spec).run() if o.status is Status.FAIL]
    assert fails == [], f"Risk engine failed for {name}: {fails}"


@pytest.mark.parametrize(("name", "node_type", "family"), _FAMILIES)
def test_new_family_terraform_emit(
    tmp_path: Path, name: str, node_type: NodeType, family: FindingFamily
) -> None:
    spec = _spec(name)
    bundle = TemplateGenerator().generate(spec)
    out_dir = tmp_path / f"tf_{name}"
    written = TerraformEmitter(bundle.graph).emit(out_dir)
    assert len(written) == len(constants.TERRAFORM_FILES)
    for p in written:
        content = p.read_text(encoding="utf-8")
        for forbidden in constants.FORBIDDEN_PERMISSION_PATTERNS:
            stem = forbidden.split("*")[0]
            assert stem not in content


@pytest.mark.parametrize(("name", "node_type", "family"), _FAMILIES)
def test_new_family_composer_generates(
    name: str, node_type: NodeType, family: FindingFamily
) -> None:
    spec = _spec(name)
    spec.scale_profile = "small"
    bundle = GraphComposer(spec, seed=42).generate()
    assert any(n.type is node_type for n in bundle.graph.nodes)
    assert any(f.family == family for f in bundle.findings.findings)
    assert len(bundle.ground_truth.paths) >= 1
