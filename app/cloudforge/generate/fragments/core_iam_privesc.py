"""``core.iam_privesc_policy_version``: IAM policy-version privilege escalation.

Story: a developer role holds ``iam:CreatePolicyVersion`` and
``iam:SetDefaultPolicyVersion`` on the managed policy attached to AppOperatorRole,
a role it can reach by ``sts:AssumeRole`` (directly on the direct chain, through
``extra_hops`` intermediate roles otherwise). Publishing a new default version
makes that role admin-capable in the developer's hands. What the attacker reaches
is the role (``sink_kind`` ``role``); the payroll data the role can read today is
the second, high-severity path. With ``dead_end`` the developer can also assume a
second role whose grant reaches nothing.
"""

from __future__ import annotations

from random import Random
from typing import Any

from app.cloudforge.generate.fragments import _aws_shape as aws
from app.cloudforge.generate.fragments._core import Kit, draw_hops, hop_lines, shape_of
from app.cloudforge.generate.fragments._vocab import AWS_HOP_ROLES
from app.cloudforge.generate.fragments.base import FragmentBundle, register_core
from app.cloudforge.models.findings import (
    ExpectedFinding,
    FindingFamily,
    GroundTruthPath,
    SinkKind,
)
from app.cloudforge.models.graph import EdgeType, GraphEdge, GraphNode, NodeTags, NodeType

_TAGS = NodeTags(env="prod", owner="identity-security", app="iam-lifecycle")
_TARGET_POLICY_ARN = "arn:aws:iam::000000000000:policy/AppOperatorDataPolicy"
_ENTRY = "role-developer"
_SINK = "role-app-operator"


@register_core
class IamPrivescPolicyVersion:
    scenario_type = "iam_privesc_policy_version"
    cloud = "aws"
    prompt = (
        "An internal developer identity has been provisioned with limited scope. "
        "Can it reach a role that administers the account, and how?"
    )
    checklist = ("iam_privesc_policy_version", "IAM: CreatePolicyVersion Escalation")
    teaching_point = (
        "`iam:CreatePolicyVersion` to an admin-capable role; its payroll read is a second path"
    )

    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        kit = Kit(ns, _TAGS)
        shape = shape_of(params)
        hops = draw_hops(kit, rng, shape.extra_hops, AWS_HOP_ROLES, "role", NodeType.IAM_ROLE)
        chain = [_ENTRY, *hops.ids, _SINK]
        nodes = _nodes(kit) + hops.nodes
        edges = _edges(kit, chain)
        if shape.dead_end:
            branch = aws.dead_end_role(kit, rng, _ENTRY)
            nodes, edges = nodes + branch.nodes, edges + branch.edges
        names = ["DeveloperOperationsRole", *hops.names, "AppOperatorRole"]
        return FragmentBundle(
            nodes=nodes,
            edges=edges,
            findings=_findings(kit),
            paths=[_critical(kit, chain, names), _data_path(kit)],
        )


def _nodes(kit: Kit) -> list[GraphNode]:
    return [
        kit.node("acct-main", NodeType.ACCOUNT, "prod-account", "medium"),
        kit.node(_ENTRY, NodeType.IAM_ROLE, "DeveloperOperationsRole", "high"),
        kit.node(
            "pol-dev-tools",
            NodeType.IAM_POLICY,
            "PolicyLifecycleManagementPolicy",
            "critical",
            actions=["iam:CreatePolicyVersion", "iam:SetDefaultPolicyVersion"],
            resource=_TARGET_POLICY_ARN,
        ),
        kit.node(_SINK, NodeType.IAM_ROLE, "AppOperatorRole", "high"),
        kit.node(
            "pol-target-app",
            NodeType.IAM_POLICY,
            "AppOperatorDataPolicy",
            "high",
            actions=["s3:Get*", "s3:List*"],
        ),
        kit.node(
            "s3-payroll-records",
            NodeType.S3_BUCKET,
            "payroll-records-prod-000000000000",
            "critical",
        ),
        kit.node(
            "data-payroll-records",
            NodeType.DATASET,
            "payroll-financial-records",
            "critical",
            classification="restricted",
        ),
    ]


def _edges(kit: Kit, chain: list[str]) -> list[GraphEdge]:
    return [
        kit.edge("acct-main", _ENTRY, EdgeType.ASSUMES, "none"),
        kit.edge(_ENTRY, "pol-dev-tools", EdgeType.ATTACHED_POLICY, "critical"),
        *kit.chain(chain, EdgeType.ASSUMES, "critical"),
        kit.edge(_SINK, "pol-target-app", EdgeType.ATTACHED_POLICY, "high"),
        kit.edge(_SINK, "s3-payroll-records", EdgeType.CAN_READ, "critical"),
        kit.edge(
            "s3-payroll-records",
            "data-payroll-records",
            EdgeType.STORES_SENSITIVE_DATA,
            "none",
        ),
    ]


def _findings(kit: Kit) -> list[ExpectedFinding]:
    return [
        ExpectedFinding(
            id=kit.nid("finding-iam-privesc-policy-version-01"),
            severity="critical",
            family=FindingFamily.IAM_PRIVESC_POLICY_VERSION,
            resource_ids=[kit.nid(_ENTRY), kit.nid("pol-dev-tools")],
            expected_scanner_visibility="partial",
            ground_truth=(
                "Role possesses iam:CreatePolicyVersion permitting policy privilege escalation"
            ),
            remediation="Enforce an iam:PermissionsBoundary on all non-admin IAM roles",
        ),
        ExpectedFinding(
            id=kit.nid("finding-iam-excessive-privilege-01"),
            severity="high",
            family=FindingFamily.IAM_EXCESSIVE_PRIVILEGE,
            resource_ids=[kit.nid(_SINK), kit.nid("pol-target-app")],
            expected_scanner_visibility="visible",
            ground_truth="Role holds broad s3:Get* and s3:List* actions on sensitive data",
            remediation="Scope policy to exact s3:GetObject on specific prefixes",
        ),
    ]


def _critical(kit: Kit, chain: list[str], names: list[str]) -> GroundTruthPath:
    return GroundTruthPath(
        id=kit.nid("path-critical-privesc-01"),
        severity="critical",
        nodes=[kit.nid(n) for n in chain],
        edges=kit.chain_keys(chain, EdgeType.ASSUMES),
        sink_kind=SinkKind.ROLE,
        target=kit.nid(_SINK),
        explanation=(
            "DeveloperOperationsRole holds iam:CreatePolicyVersion and "
            f"iam:SetDefaultPolicyVersion on AppOperatorDataPolicy; {hop_lines(names, 'assumes')}"
            ": a new default version makes AppOperatorRole admin-capable"
        ),
    )


def _data_path(kit: Kit) -> GroundTruthPath:
    return GroundTruthPath(
        id=kit.nid("path-high-privesc-data-01"),
        severity="high",
        nodes=[kit.nid(_SINK), kit.nid("s3-payroll-records"), kit.nid("data-payroll-records")],
        edges=[
            kit.ek(_SINK, EdgeType.CAN_READ, "s3-payroll-records"),
            kit.ek("s3-payroll-records", EdgeType.STORES_SENSITIVE_DATA, "data-payroll-records"),
        ],
        sink_kind=SinkKind.DATA,
        target=kit.nid("data-payroll-records"),
        explanation=(
            "AppOperatorRole already reads payroll-records: what the escalated role "
            "can read before any policy is rewritten"
        ),
    )
