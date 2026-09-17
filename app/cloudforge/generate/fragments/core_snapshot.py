"""``core.public_ebs_snapshot``: an unencrypted EBS snapshot shared with ``all``.

What the attacker reaches is the snapshot itself (``sink_kind`` ``snapshot``):
anyone can create a volume from it. The warehouse records the snapshot was cut
from live in the estate behind the locked backups bucket, off the graded path.
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

_TAGS = NodeTags(env="prod", owner="data-platform-team", app="analytics-warehouse")


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


@register("core.public_ebs_snapshot")
class PublicEbsSnapshot:
    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        return FragmentBundle(
            nodes=_nodes(ns),
            edges=_edges(ns),
            findings=_findings(ns),
            paths=[_critical(ns)],
        )


def _nodes(ns: str) -> list[GraphNode]:
    return [
        _node(ns, "acct-main", NodeType.ACCOUNT, "prod-account", "high"),
        _node(
            ns,
            "snap-public",
            NodeType.EBS_SNAPSHOT,
            "warehouse-snapshot",
            "critical",
            public="true",
            encrypted="false",
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
        _node(ns, "app-warehouse", NodeType.APPLICATION, "analytics-warehouse", "medium"),
        _node(
            ns,
            "data-warehouse",
            NodeType.DATASET,
            "warehouse-records",
            "critical",
            classification="restricted",
        ),
        _node(ns, "trail-main", NodeType.LOG_TRAIL, "main-trail", "medium"),
    ]


def _edges(ns: str) -> list[GraphEdge]:
    return [
        _edge(ns, "acct-main", "snap-public", EdgeType.EXPOSED_TO_INTERNET, "critical"),
        _edge(ns, "snap-public", "app-warehouse", EdgeType.BELONGS_TO_APP, "low"),
        _edge(ns, "s3-locked-backups", "app-warehouse", EdgeType.BELONGS_TO_APP, "low"),
        _edge(ns, "s3-locked-backups", "data-warehouse", EdgeType.STORES_SENSITIVE_DATA, "none"),
    ]


def _critical(ns: str) -> GroundTruthPath:
    return GroundTruthPath(
        id=_nid(ns, "path-critical-snap-01"),
        severity="critical",
        nodes=[_nid(ns, "acct-main"), _nid(ns, "snap-public")],
        edges=[
            (
                f"{_nid(ns, 'acct-main')}->{EdgeType.EXPOSED_TO_INTERNET.value}"
                f"->{_nid(ns, 'snap-public')}"
            ),
        ],
        sink_kind=SinkKind.SNAPSHOT,
        target=_nid(ns, "snap-public"),
        explanation=(
            "The warehouse snapshot is unencrypted and public (create-volume "
            "permission group all), so anyone can create a volume from it and read "
            "the warehouse records it was cut from."
        ),
    )


def _findings(ns: str) -> list[ExpectedFinding]:
    return [_public_finding(ns), _fp_finding(ns)]


def _public_finding(ns: str) -> ExpectedFinding:
    return ExpectedFinding(
        id=_nid(ns, "find-snap-01"),
        severity="high",
        family=FindingFamily.EBS_SNAPSHOT_PUBLIC,
        resource_ids=[_nid(ns, "snap-public")],
        expected_scanner_visibility="visible",
        ground_truth="The warehouse snapshot is public and unencrypted.",
        remediation="Remove group=all create-volume permission and encrypt snapshots.",
    )


def _fp_finding(ns: str) -> ExpectedFinding:
    return ExpectedFinding(
        id=_nid(ns, "find-snap-fp-01"),
        severity="low",
        family=FindingFamily.PUBLIC_LOOKING_BUCKET_WITH_COMPENSATING_CONTROL,
        resource_ids=[_nid(ns, "s3-locked-backups")],
        expected_scanner_visibility="visible",
        ground_truth="benign",
        remediation="None needed — a bucket policy restricts access despite the name.",
    )
