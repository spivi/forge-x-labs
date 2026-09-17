"""``core.public_ebs_snapshot``: an unencrypted EBS snapshot shared with ``all``.

What the attacker reaches is the snapshot itself (``sink_kind`` ``snapshot``):
anyone can create a volume from it. The warehouse records the snapshot was cut
from live in the estate behind the locked backups bucket, off the graded path.

Difficulty adds, through the composer's shape: a public-looking bucket the
account exposes that a policy locks down (``dead_end``), a lookalike snapshot
that is shared the same way but encrypted, so nobody outside can use it
(``lookalike``), and an application identity route to the same snapshot
(``prefix_hops``), labeled as its own high-severity path.
"""

from __future__ import annotations

from random import Random
from typing import Any

from app.cloudforge.generate.fragments import _aws_shape as aws
from app.cloudforge.generate.fragments._core import Kit, Piece, shape_of
from app.cloudforge.generate.fragments._vocab import LOOKALIKE_SNAPSHOTS
from app.cloudforge.generate.fragments.base import FragmentBundle, register
from app.cloudforge.models.findings import (
    ExpectedFinding,
    FindingFamily,
    GroundTruthPath,
    SinkKind,
)
from app.cloudforge.models.graph import EdgeType, GraphEdge, GraphNode, NodeTags, NodeType

_TAGS = NodeTags(env="prod", owner="data-platform-team", app="analytics-warehouse")
_ENTRY = "acct-main"
_SINK = "snap-public"


@register("core.public_ebs_snapshot")
class PublicEbsSnapshot:
    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        kit = Kit(ns, _TAGS)
        extra = aws.extend(kit, rng, shape_of(params), _story(), _lookalike)
        return FragmentBundle(
            nodes=_nodes(kit) + extra.nodes,
            edges=_edges(kit) + extra.edges,
            findings=_findings(kit) + extra.findings,
            paths=[_critical(kit), *extra.paths],
        )


def _story() -> aws.Story:
    return aws.Story(
        entry=_ENTRY,
        resource=_SINK,
        tail=[_SINK],
        tail_edges=[],
        actions=["ec2:DescribeSnapshots", "ec2:CreateVolume"],
        sink_kind=SinkKind.SNAPSHOT,
        stem="snap",
        dead_end=aws.dead_end_bucket,
    )


def _lookalike(kit: Kit, rng: Random) -> Piece:
    return aws.lookalike(
        kit,
        rng,
        _ENTRY,
        EdgeType.EXPOSED_TO_INTERNET,
        "snap",
        NodeType.EBS_SNAPSHOT,
        LOOKALIKE_SNAPSHOTS,
        public="true",
        encrypted="true",
    )


def _nodes(kit: Kit) -> list[GraphNode]:
    return [
        kit.node(_ENTRY, NodeType.ACCOUNT, "prod-account", "high"),
        kit.node(
            _SINK,
            NodeType.EBS_SNAPSHOT,
            "warehouse-snapshot",
            "critical",
            public="true",
            encrypted="false",
        ),
        kit.node(
            "s3-locked-backups",
            NodeType.S3_BUCKET,
            "public-looking-backups",
            "medium",
            public_access="enabled",
            compensating_control="true",
        ),
        kit.node("app-warehouse", NodeType.APPLICATION, "analytics-warehouse", "medium"),
        kit.node(
            "data-warehouse",
            NodeType.DATASET,
            "warehouse-records",
            "critical",
            classification="restricted",
        ),
        kit.node("trail-main", NodeType.LOG_TRAIL, "main-trail", "medium"),
    ]


def _edges(kit: Kit) -> list[GraphEdge]:
    return [
        kit.edge(_ENTRY, _SINK, EdgeType.EXPOSED_TO_INTERNET, "critical"),
        kit.edge(_SINK, "app-warehouse", EdgeType.BELONGS_TO_APP, "low"),
        kit.edge("s3-locked-backups", "app-warehouse", EdgeType.BELONGS_TO_APP, "low"),
        kit.edge("s3-locked-backups", "data-warehouse", EdgeType.STORES_SENSITIVE_DATA, "none"),
    ]


def _critical(kit: Kit) -> GroundTruthPath:
    return GroundTruthPath(
        id=kit.nid("path-critical-snap-01"),
        severity="critical",
        nodes=[kit.nid(_ENTRY), kit.nid(_SINK)],
        edges=[kit.ek(_ENTRY, EdgeType.EXPOSED_TO_INTERNET, _SINK)],
        sink_kind=SinkKind.SNAPSHOT,
        target=kit.nid(_SINK),
        explanation=(
            "The warehouse snapshot is unencrypted and public (create-volume "
            "permission group all), so anyone can create a volume from it and read "
            "the warehouse records it was cut from."
        ),
    )


def _findings(kit: Kit) -> list[ExpectedFinding]:
    return [_public_finding(kit), _fp_finding(kit)]


def _public_finding(kit: Kit) -> ExpectedFinding:
    return ExpectedFinding(
        id=kit.nid("find-snap-01"),
        severity="high",
        family=FindingFamily.EBS_SNAPSHOT_PUBLIC,
        resource_ids=[kit.nid(_SINK)],
        expected_scanner_visibility="visible",
        ground_truth="The warehouse snapshot is public and unencrypted.",
        remediation="Remove group=all create-volume permission and encrypt snapshots.",
    )


def _fp_finding(kit: Kit) -> ExpectedFinding:
    return ExpectedFinding(
        id=kit.nid("find-snap-fp-01"),
        severity="low",
        family=FindingFamily.PUBLIC_LOOKING_BUCKET_WITH_COMPENSATING_CONTROL,
        resource_ids=[kit.nid("s3-locked-backups")],
        expected_scanner_visibility="visible",
        ground_truth="benign",
        remediation="None needed: a bucket policy restricts access despite the name.",
    )
