"""``core.cross_account_trust`` fragment — external account trusted into data.

Story: a dummy partner account (``999999999999``) is trusted by a SharedRole
that can ``s3:Get*/List*`` a sensitive partner-exchange bucket. The critical
path is the cross-account assume, not a public bucket or a PassRole chain.
"""

from __future__ import annotations

from random import Random
from typing import Any

from app.cloudforge import constants
from app.cloudforge.generate.fragments.base import FragmentBundle, register
from app.cloudforge.models.findings import ExpectedFinding, FindingFamily, GroundTruthPath
from app.cloudforge.models.graph import (
    EdgeSecurity,
    EdgeType,
    GraphEdge,
    GraphNode,
    NodeSecurity,
    NodeTags,
    NodeType,
)

_TAGS = NodeTags(env="prod", owner="partner-integrations", app="partner-exchange")
_EXT = constants.EXTERNAL_DUMMY_ACCOUNT_ID
_TRUST = f"arn:aws:iam::{_EXT}:root"
_BUCKET_ARN = "arn:aws:s3:::partner-exchange"


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


@register("core.cross_account_trust")
class CrossAccountTrust:
    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        return FragmentBundle(
            nodes=_nodes(ns),
            edges=_edges(ns),
            findings=_findings(ns),
            paths=[_critical(ns)],
        )


def _nodes(ns: str) -> list[GraphNode]:
    return [
        _node(ns, "acct-external", NodeType.ACCOUNT, "partner-account", "high", account_id=_EXT),
        _node(ns, "acct-main", NodeType.ACCOUNT, "prod-account", "medium"),
        _node(
            ns,
            "role-shared",
            NodeType.IAM_ROLE,
            "SharedRole",
            "critical",
            trusted_principal=_TRUST,
        ),
        _node(
            ns,
            "pol-shared-s3read",
            NodeType.IAM_POLICY,
            "SharedS3ReadPolicy",
            "high",
            actions=["s3:Get*", "s3:List*"],
            resource=f"{_BUCKET_ARN}/*",
        ),
        _node(
            ns,
            "s3-partner-data",
            NodeType.S3_BUCKET,
            "partner-exchange",
            "critical",
            logging="disabled",
        ),
        _node(
            ns,
            "s3-locked-backups",
            NodeType.S3_BUCKET,
            "public-looking-backups",
            "medium",
            public_access="enabled",
            compensating_control="true",
        ),
        _node(ns, "app-partner-exchange", NodeType.APPLICATION, "partner-exchange", "medium"),
        _node(ns, "data-partner", NodeType.DATASET, "partner-records", "critical"),
        _node(ns, "trail-main", NodeType.LOG_TRAIL, "main-trail", "medium"),
    ]


def _edges(ns: str) -> list[GraphEdge]:
    return [
        _edge(ns, "acct-external", "role-shared", EdgeType.ASSUMES, "critical"),
        _edge(ns, "role-shared", "pol-shared-s3read", EdgeType.ATTACHED_POLICY, "high"),
        _edge(ns, "role-shared", "s3-partner-data", EdgeType.CAN_READ, "critical"),
        _edge(ns, "s3-partner-data", "data-partner", EdgeType.STORES_SENSITIVE_DATA, "critical"),
        _edge(ns, "s3-partner-data", "app-partner-exchange", EdgeType.BELONGS_TO_APP, "low"),
        _edge(ns, "s3-locked-backups", "app-partner-exchange", EdgeType.BELONGS_TO_APP, "low"),
    ]


def _critical(ns: str) -> GroundTruthPath:
    return GroundTruthPath(
        id=_nid(ns, "path-critical-xacct-01"),
        severity="critical",
        nodes=[
            _nid(ns, "acct-external"),
            _nid(ns, "role-shared"),
            _nid(ns, "s3-partner-data"),
            _nid(ns, "data-partner"),
        ],
        edges=[
            f"{_nid(ns, 'acct-external')}->{EdgeType.ASSUMES.value}->{_nid(ns, 'role-shared')}",
            f"{_nid(ns, 'role-shared')}->{EdgeType.CAN_READ.value}->{_nid(ns, 's3-partner-data')}",
            (
                f"{_nid(ns, 's3-partner-data')}->{EdgeType.STORES_SENSITIVE_DATA.value}"
                f"->{_nid(ns, 'data-partner')}"
            ),
        ],
        explanation=(
            "Partner account 999999999999 is trusted to assume SharedRole; "
            "SharedRole holds s3:Get*/List* on partner-exchange, which stores "
            "sensitive partner records."
        ),
    )


def _findings(ns: str) -> list[ExpectedFinding]:
    return [_trust_finding(ns), _logging_finding(ns), _false_positive_finding(ns)]


def _trust_finding(ns: str) -> ExpectedFinding:
    return ExpectedFinding(
        id=_nid(ns, "find-xacct-01"),
        severity="critical",
        family=FindingFamily.IAM_CROSS_ACCOUNT_TRUST,
        resource_ids=[
            _nid(ns, "acct-external"),
            _nid(ns, "role-shared"),
            _nid(ns, "pol-shared-s3read"),
            _nid(ns, "s3-partner-data"),
        ],
        expected_scanner_visibility="partial",
        ground_truth="An external dummy account is trusted into a role that can read data.",
        remediation="Restrict the trust policy to a named partner role, not account root.",
    )


def _logging_finding(ns: str) -> ExpectedFinding:
    return ExpectedFinding(
        id=_nid(ns, "find-xacct-logging-01"),
        severity="medium",
        family=FindingFamily.S3_LOGGING_MISSING,
        resource_ids=[_nid(ns, "s3-partner-data"), _nid(ns, "trail-main")],
        expected_scanner_visibility="visible",
        ground_truth="The partner-exchange bucket has no access logging.",
        remediation="Enable S3 access logging and CloudTrail data events for the bucket.",
    )


def _false_positive_finding(ns: str) -> ExpectedFinding:
    return ExpectedFinding(
        id=_nid(ns, "find-xacct-fp-01"),
        severity="low",
        family=FindingFamily.PUBLIC_LOOKING_BUCKET_WITH_COMPENSATING_CONTROL,
        resource_ids=[_nid(ns, "s3-locked-backups")],
        expected_scanner_visibility="visible",
        ground_truth="benign",
        remediation="None needed — a bucket policy restricts access despite the name.",
    )
