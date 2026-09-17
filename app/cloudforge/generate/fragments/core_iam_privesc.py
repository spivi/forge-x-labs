"""``core.iam_privesc_policy_version``: IAM policy-version privilege escalation.

Story: a developer role holds ``iam:CreatePolicyVersion`` and
``iam:SetDefaultPolicyVersion`` on the managed policy attached to AppOperatorRole,
a role it can also assume. Publishing a new default version makes that role
admin-capable in the developer's hands. What the attacker reaches is the role
(``sink_kind`` ``role``); the payroll data the role can read today is the second,
high-severity path.
"""

from __future__ import annotations

from random import Random
from typing import Any

from app.cloudforge.generate.fragments.base import FragmentBundle, register
from app.cloudforge.models.findings import (
    ExpectedFinding,
    FindingFamily,
    GroundTruthPath,
    SinkKind,
)
from app.cloudforge.models.graph import (
    EdgeSecurity,
    EdgeType,
    GraphEdge,
    GraphNode,
    NodeSecurity,
    NodeTags,
    NodeType,
)

_TAGS = NodeTags(env="prod", owner="identity-security", app="iam-lifecycle")
_TARGET_POLICY_ARN = "arn:aws:iam::000000000000:policy/AppOperatorDataPolicy"


def _nid(ns: str, node_id: str) -> str:
    return f"{ns}/{node_id}" if ns else node_id


def _node(
    ns: str, node_id: str, node_type: NodeType, name: str, crit: str, **attrs: str | list[str]
) -> GraphNode:
    return GraphNode(
        id=_nid(ns, node_id),
        type=node_type,
        name=name,
        tags=_TAGS,
        security=NodeSecurity(criticality=crit),
        attributes=dict(attrs),
    )


def _edge(ns: str, src: str, dst: str, edge_type: EdgeType, risk: str) -> GraphEdge:
    return GraphEdge(
        from_=_nid(ns, src),
        to=_nid(ns, dst),
        type=edge_type,
        security=EdgeSecurity(risk=risk),
    )


@register("core.iam_privesc_policy_version")
class IamPrivescPolicyVersion:
    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        return FragmentBundle(
            nodes=_nodes(ns),
            edges=_edges(ns),
            findings=_findings(ns),
            paths=[_critical(ns), _data_path(ns)],
        )


def _nodes(ns: str) -> list[GraphNode]:
    return [
        _node(ns, "acct-main", NodeType.ACCOUNT, "prod-account", "medium"),
        _node(ns, "role-developer", NodeType.IAM_ROLE, "DeveloperOperationsRole", "high"),
        _node(
            ns,
            "pol-dev-tools",
            NodeType.IAM_POLICY,
            "PolicyLifecycleManagementPolicy",
            "critical",
            actions=["iam:CreatePolicyVersion", "iam:SetDefaultPolicyVersion"],
            resource=_TARGET_POLICY_ARN,
        ),
        _node(ns, "role-app-operator", NodeType.IAM_ROLE, "AppOperatorRole", "high"),
        _node(
            ns,
            "pol-target-app",
            NodeType.IAM_POLICY,
            "AppOperatorDataPolicy",
            "high",
            actions=["s3:Get*", "s3:List*"],
        ),
        _node(
            ns,
            "s3-payroll-records",
            NodeType.S3_BUCKET,
            "payroll-records-prod-000000000000",
            "critical",
        ),
        _node(
            ns,
            "data-payroll-records",
            NodeType.DATASET,
            "payroll-financial-records",
            "critical",
            classification="restricted",
        ),
    ]


def _edges(ns: str) -> list[GraphEdge]:
    return [
        _edge(ns, "acct-main", "role-developer", EdgeType.ASSUMES, "none"),
        _edge(ns, "role-developer", "pol-dev-tools", EdgeType.ATTACHED_POLICY, "critical"),
        _edge(ns, "role-developer", "role-app-operator", EdgeType.ASSUMES, "critical"),
        _edge(ns, "role-app-operator", "pol-target-app", EdgeType.ATTACHED_POLICY, "high"),
        _edge(ns, "role-app-operator", "s3-payroll-records", EdgeType.CAN_READ, "critical"),
        _edge(
            ns,
            "s3-payroll-records",
            "data-payroll-records",
            EdgeType.STORES_SENSITIVE_DATA,
            "none",
        ),
    ]


def _findings(ns: str) -> list[ExpectedFinding]:
    return [
        ExpectedFinding(
            id=_nid(ns, "finding-iam-privesc-policy-version-01"),
            severity="critical",
            family=FindingFamily.IAM_PRIVESC_POLICY_VERSION,
            resource_ids=[_nid(ns, "role-developer"), _nid(ns, "pol-dev-tools")],
            expected_scanner_visibility="partial",
            ground_truth=(
                "Role possesses iam:CreatePolicyVersion permitting policy privilege escalation"
            ),
            remediation="Enforce an iam:PermissionsBoundary on all non-admin IAM roles",
        ),
        ExpectedFinding(
            id=_nid(ns, "finding-iam-excessive-privilege-01"),
            severity="high",
            family=FindingFamily.IAM_EXCESSIVE_PRIVILEGE,
            resource_ids=[_nid(ns, "role-app-operator"), _nid(ns, "pol-target-app")],
            expected_scanner_visibility="visible",
            ground_truth="Role holds broad s3:Get* and s3:List* actions on sensitive data",
            remediation="Scope policy to exact s3:GetObject on specific prefixes",
        ),
    ]


def _ek(ns: str, src: str, edge_type: EdgeType, dst: str) -> str:
    return f"{_nid(ns, src)}->{edge_type.value}->{_nid(ns, dst)}"


def _critical(ns: str) -> GroundTruthPath:
    return GroundTruthPath(
        id=_nid(ns, "path-critical-privesc-01"),
        severity="critical",
        nodes=[_nid(ns, "role-developer"), _nid(ns, "role-app-operator")],
        edges=[_ek(ns, "role-developer", EdgeType.ASSUMES, "role-app-operator")],
        sink_kind=SinkKind.ROLE,
        target=_nid(ns, "role-app-operator"),
        explanation=(
            "DeveloperOperationsRole holds iam:CreatePolicyVersion and "
            "iam:SetDefaultPolicyVersion on AppOperatorDataPolicy and can assume "
            "AppOperatorRole: a new default version makes that role admin-capable"
        ),
    )


def _data_path(ns: str) -> GroundTruthPath:
    return GroundTruthPath(
        id=_nid(ns, "path-high-privesc-data-01"),
        severity="high",
        nodes=[
            _nid(ns, "role-app-operator"),
            _nid(ns, "s3-payroll-records"),
            _nid(ns, "data-payroll-records"),
        ],
        edges=[
            _ek(ns, "role-app-operator", EdgeType.CAN_READ, "s3-payroll-records"),
            _ek(ns, "s3-payroll-records", EdgeType.STORES_SENSITIVE_DATA, "data-payroll-records"),
        ],
        sink_kind=SinkKind.DATA,
        target=_nid(ns, "data-payroll-records"),
        explanation=(
            "AppOperatorRole already reads payroll-records: what the escalated role "
            "can read before any policy is rewritten"
        ),
    )
