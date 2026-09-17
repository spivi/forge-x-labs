"""``core.kms_key_overbroad`` — KMS key policy grants Decrypt to ``*``."""

from __future__ import annotations

from random import Random
from typing import Any

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

_TAGS = NodeTags(env="prod", owner="data-platform-team", app="secrets-store")


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


@register("core.kms_key_overbroad")
class KmsKeyOverbroad:
    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        return FragmentBundle(
            nodes=_nodes(ns),
            edges=_edges(ns),
            findings=_findings(ns),
            paths=[_critical(ns)],
        )


def _nodes(ns: str) -> list[GraphNode]:
    return [
        _node(ns, "acct-main", NodeType.ACCOUNT, "prod-account", "medium"),
        _node(ns, "role-reader", NodeType.IAM_ROLE, "SecretsReader", "high"),
        _node(
            ns,
            "pol-reader",
            NodeType.IAM_POLICY,
            "SecretsReaderPolicy",
            "high",
            actions=["kms:Decrypt", "s3:Get*", "s3:List*"],
            resource="*",
        ),
        _node(
            ns,
            "kms-data",
            NodeType.KMS_KEY,
            "customer-data-key",
            "critical",
            principal="*",
            actions=["kms:Decrypt"],
        ),
        _node(
            ns,
            "s3-encrypted",
            NodeType.S3_BUCKET,
            "encrypted-exports",
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
        _node(ns, "app-secrets-store", NodeType.APPLICATION, "secrets-store", "medium"),
        _node(
            ns,
            "data-secrets",
            NodeType.DATASET,
            "customer-secrets",
            "critical",
            classification="restricted",
        ),
        _node(ns, "trail-main", NodeType.LOG_TRAIL, "main-trail", "medium"),
    ]


def _edges(ns: str) -> list[GraphEdge]:
    return [
        _edge(ns, "role-reader", "pol-reader", EdgeType.ATTACHED_POLICY, "high"),
        _edge(ns, "role-reader", "kms-data", EdgeType.CAN_DECRYPT, "high"),
        _edge(ns, "role-reader", "s3-encrypted", EdgeType.CAN_READ, "critical"),
        _edge(ns, "s3-encrypted", "data-secrets", EdgeType.STORES_SENSITIVE_DATA, "critical"),
        _edge(ns, "s3-encrypted", "app-secrets-store", EdgeType.BELONGS_TO_APP, "low"),
        _edge(ns, "s3-locked-backups", "app-secrets-store", EdgeType.BELONGS_TO_APP, "low"),
    ]


def _critical(ns: str) -> GroundTruthPath:
    return GroundTruthPath(
        id=_nid(ns, "path-critical-kms-01"),
        severity="critical",
        nodes=[
            _nid(ns, "role-reader"),
            _nid(ns, "s3-encrypted"),
            _nid(ns, "data-secrets"),
        ],
        edges=[
            f"{_nid(ns, 'role-reader')}->{EdgeType.CAN_READ.value}->{_nid(ns, 's3-encrypted')}",
            (
                f"{_nid(ns, 's3-encrypted')}->{EdgeType.STORES_SENSITIVE_DATA.value}"
                f"->{_nid(ns, 'data-secrets')}"
            ),
        ],
        explanation=(
            "The customer-data-key policy grants kms:Decrypt to *; SecretsReader "
            "can decrypt and read encrypted-exports, which stores customer secrets."
        ),
    )


def _findings(ns: str) -> list[ExpectedFinding]:
    return [_kms_finding(ns), _logging_finding(ns), _fp_finding(ns)]


def _kms_finding(ns: str) -> ExpectedFinding:
    return ExpectedFinding(
        id=_nid(ns, "find-kms-01"),
        severity="critical",
        family=FindingFamily.KMS_KEY_POLICY_OVERBROAD,
        resource_ids=[
            _nid(ns, "kms-data"),
            _nid(ns, "role-reader"),
            _nid(ns, "pol-reader"),
        ],
        expected_scanner_visibility="partial",
        ground_truth="KMS key policy allows kms:Decrypt from any AWS principal.",
        remediation="Restrict the key policy principal to the SecretsReader role.",
    )


def _logging_finding(ns: str) -> ExpectedFinding:
    return ExpectedFinding(
        id=_nid(ns, "find-kms-logging-01"),
        severity="medium",
        family=FindingFamily.S3_LOGGING_MISSING,
        resource_ids=[_nid(ns, "s3-encrypted"), _nid(ns, "trail-main")],
        expected_scanner_visibility="visible",
        ground_truth="The encrypted-exports bucket has no access logging.",
        remediation="Enable S3 access logging and CloudTrail data events.",
    )


def _fp_finding(ns: str) -> ExpectedFinding:
    return ExpectedFinding(
        id=_nid(ns, "find-kms-fp-01"),
        severity="low",
        family=FindingFamily.PUBLIC_LOOKING_BUCKET_WITH_COMPENSATING_CONTROL,
        resource_ids=[_nid(ns, "s3-locked-backups")],
        expected_scanner_visibility="visible",
        ground_truth="benign",
        remediation="None needed — a bucket policy restricts access despite the name.",
    )
