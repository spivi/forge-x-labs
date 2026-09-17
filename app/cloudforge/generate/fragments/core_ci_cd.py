"""``core.ci_cd_iam_chain`` fragment: a parameterized CI/CD-to-data IAM chain.

Story: a GitHub Actions OIDC identity assumes a DeployRole, which can
``iam:PassRole`` a chain of intermediate roles (``extra_hops`` of them, drawn
by the composer from the difficulty band) before reaching a RuntimeRole that
holds broad S3 read over a sensitive customer-exports bucket. That chain is the
critical risk. Supporting findings: an overly-broad S3 read, a missing-logging
gap, an over-exposed security group, and one benign false-positive (a
public-looking bucket with a compensating control). With ``dead_end`` the CI
identity can also assume a second role whose grant reaches nothing.

Node/edge builders live in ``core_ci_cd_nodes.py``; the AWS dead end in
``_aws_shape``. ``path_hops`` is still honored as the legacy spelling of the
chain length (``path_hops - 3`` extra hops).
"""

from __future__ import annotations

from random import Random
from typing import Any

from app.cloudforge.generate.fragments import _aws_shape as aws
from app.cloudforge.generate.fragments import core_ci_cd_nodes as parts
from app.cloudforge.generate.fragments._core import Kit, hop_lines, shape_of
from app.cloudforge.generate.fragments.base import FragmentBundle, register_core
from app.cloudforge.models.findings import (
    ExpectedFinding,
    FindingFamily,
    GroundTruthPath,
    SinkKind,
)
from app.cloudforge.models.graph import EdgeType

_DEFAULT_HOPS = 3
_ENTRY = "cicd-github"


def _extra_hops(params: dict[str, Any]) -> int:
    if "path_hops" in params and "extra_hops" not in params:
        return max(0, int(params["path_hops"]) - _DEFAULT_HOPS)
    return shape_of(params).extra_hops


@register_core
class CiCdIamChain:
    scenario_type = "ci_cd_iam_chain"
    cloud = "aws"
    prompt = (
        "A CI identity deploys into this account. Can it reach sensitive customer "
        "data? Which issues are real, and which look worse than they are?"
    )
    checklist = ("iam_passrole_risk", "IAM: PassRole Escalation Chain")
    teaching_point = "CI OIDC identity -> PassRole -> sensitive data"

    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        kit = Kit(ns, parts.TAGS)
        hops = parts.hop_nodes(kit, rng, _extra_hops(params))
        chain = ["role-deploy", *hops.ids, "role-runtime"]
        nodes = parts.fixed_nodes(kit) + hops.nodes
        edges = parts.fixed_edges(kit) + parts.pass_role_chain(kit, chain)
        if shape_of(params).dead_end:
            branch = aws.dead_end_role(kit, rng, _ENTRY)
            nodes, edges = nodes + branch.nodes, edges + branch.edges
        findings = _findings(kit, chain)
        path = _critical(kit, chain, ["DeployRole", *hops.names, "RuntimeRole"])
        return FragmentBundle(nodes=nodes, edges=edges, findings=findings, paths=[path])


def _critical(kit: Kit, chain: list[str], names: list[str]) -> GroundTruthPath:
    nodes = [_ENTRY, *chain, "s3-customer-exports", "data-customer-exports"]
    edges = [
        kit.ek(_ENTRY, EdgeType.ASSUMES, "role-deploy"),
        *kit.chain_keys(chain, EdgeType.CAN_PASS_ROLE),
        kit.ek("role-runtime", EdgeType.CAN_READ, "s3-customer-exports"),
        kit.ek("s3-customer-exports", EdgeType.STORES_SENSITIVE_DATA, "data-customer-exports"),
    ]
    return GroundTruthPath(
        id=kit.nid("path-critical-01"),
        severity="critical",
        nodes=[kit.nid(n) for n in nodes],
        edges=edges,
        sink_kind=SinkKind.DATA,
        target=kit.nid("data-customer-exports"),
        explanation=(
            f"GitHub Actions OIDC assumes DeployRole; {hop_lines(names, 'can iam:PassRole')}; "
            "RuntimeRole holds broad s3:Get*/List* on the sensitive customer-exports "
            "bucket -> full read of customer data via CI."
        ),
    )


def _findings(kit: Kit, chain: list[str]) -> list[ExpectedFinding]:
    chain_ids = [kit.nid(step) for step in chain[:-1]]
    return [
        _passrole_finding(kit, chain_ids),
        _excessive_finding(kit),
        _logging_finding(kit),
        _sg_finding(kit),
        _false_positive_finding(kit),
    ]


def _passrole_finding(kit: Kit, chain_ids: list[str]) -> ExpectedFinding:
    return ExpectedFinding(
        id=kit.nid("find-passrole-01"),
        severity="critical",
        family=FindingFamily.IAM_PASSROLE_RISK,
        resource_ids=[*chain_ids, kit.nid("role-runtime"), kit.nid("pol-deploy-passrole")],
        expected_scanner_visibility="partial",
        ground_truth="DeployRole can pass RuntimeRole, completing the CI-to-data chain.",
        remediation="Scope iam:PassRole to the exact RuntimeRole ARN and add a role condition.",
    )


def _excessive_finding(kit: Kit) -> ExpectedFinding:
    return ExpectedFinding(
        id=kit.nid("find-s3read-01"),
        severity="high",
        family=FindingFamily.IAM_EXCESSIVE_PRIVILEGE,
        resource_ids=[
            kit.nid("role-runtime"),
            kit.nid("pol-runtime-s3read"),
            kit.nid("s3-customer-exports"),
        ],
        expected_scanner_visibility="visible",
        ground_truth="RuntimeRole has broader S3 read than intended over the exports bucket.",
        remediation="Replace s3:Get*/List* wildcards with least-privilege object prefixes.",
    )


def _logging_finding(kit: Kit) -> ExpectedFinding:
    return ExpectedFinding(
        id=kit.nid("find-logging-01"),
        severity="medium",
        family=FindingFamily.S3_LOGGING_MISSING,
        resource_ids=[kit.nid("s3-customer-exports"), kit.nid("trail-main")],
        expected_scanner_visibility="visible",
        ground_truth="The sensitive bucket has no access logging / CloudTrail data events.",
        remediation="Enable S3 access logging and CloudTrail data events for the bucket.",
    )


def _sg_finding(kit: Kit) -> ExpectedFinding:
    return ExpectedFinding(
        id=kit.nid("find-sg-01"),
        severity="medium",
        family=FindingFamily.SECURITY_GROUP_OVEREXPOSED,
        resource_ids=[kit.nid("sg-web"), kit.nid("subnet-public-a")],
        expected_scanner_visibility="visible",
        ground_truth="web-sg allows ingress from 0.0.0.0/0.",
        remediation="Restrict ingress from 0.0.0.0/0 to known corporate/CI CIDRs.",
    )


def _false_positive_finding(kit: Kit) -> ExpectedFinding:
    return ExpectedFinding(
        id=kit.nid("find-fp-01"),
        severity="low",
        family=FindingFamily.PUBLIC_LOOKING_BUCKET_WITH_COMPENSATING_CONTROL,
        resource_ids=[kit.nid("s3-public-assets")],
        expected_scanner_visibility="visible",
        ground_truth="benign",
        remediation=(
            "None needed: public read is intentional; a bucket policy limits it to GetObject."
        ),
    )
