"""``core.public_rds_instance``: a publicly accessible RDS database.

What the attacker reaches is the database itself (``sink_kind`` ``database``):
it is routable from the internet behind a 0.0.0.0/0 security group. The
financial transactions it serves also sit in a private archive bucket, off the
graded path, so the estate's data sets do not point at the exposed instance.

Difficulty adds, through the composer's shape: a public-looking bucket the
account exposes that a policy locks down (``dead_end``), a lookalike database
flagged publicly accessible but sitting behind a private security group
(``lookalike``), and an application identity route to the same database
(``prefix_hops``), labeled as its own high-severity path.
"""

from __future__ import annotations

from random import Random
from typing import Any

from app.cloudforge.generate.fragments import _aws_shape as aws
from app.cloudforge.generate.fragments._core import Kit, Piece, shape_of
from app.cloudforge.generate.fragments._vocab import LOOKALIKE_DATABASES
from app.cloudforge.generate.fragments.base import FragmentBundle, register_core
from app.cloudforge.models.findings import (
    ExpectedFinding,
    FindingFamily,
    GroundTruthPath,
    SinkKind,
)
from app.cloudforge.models.graph import EdgeType, GraphEdge, GraphNode, NodeTags, NodeType

_TAGS = NodeTags(env="prod", owner="database-team", app="billing-core")
_ENTRY = "acct-main"
_SINK = "rds-customer-db"


@register_core
class PublicRdsInstance:
    scenario_type = "public_rds_instance"
    cloud = "aws"
    prompt = (
        "A production relational database has been deployed. Can the database "
        "itself be reached from the internet, or is it isolated in private subnets?"
    )
    checklist = ("rds_instance_public", "Database: Publicly Accessible RDS Instance")
    teaching_point = "Public RDS with `0.0.0.0/0` ingress; reaches the database"

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
        actions=["rds-db:connect", "rds:DescribeDBInstances"],
        sink_kind=SinkKind.DATABASE,
        stem="rds",
        dead_end=aws.dead_end_bucket,
    )


def _lookalike(kit: Kit, rng: Random) -> Piece:
    """A database flagged publicly accessible whose security group only admits the VPC."""
    twin = aws.lookalike(
        kit,
        rng,
        _ENTRY,
        EdgeType.EXPOSED_TO_INTERNET,
        "rds",
        NodeType.RDS_INSTANCE,
        LOOKALIKE_DATABASES,
        publicly_accessible="true",
    )
    sg = kit.node(
        "sg-rds-private",
        NodeType.SECURITY_GROUP,
        "private-db-sg",
        "low",
        ingress_cidr="10.0.0.0/8",
    )
    edge = kit.edge(kit.bare(twin.nodes[0]), "sg-rds-private", EdgeType.HAS_SECURITY_GROUP, "none")
    return Piece(nodes=[*twin.nodes, sg], edges=[*twin.edges, edge])


def _nodes(kit: Kit) -> list[GraphNode]:
    return [
        kit.node(_ENTRY, NodeType.ACCOUNT, "prod-account", "medium"),
        kit.node(
            "sg-rds-public",
            NodeType.SECURITY_GROUP,
            "public-db-sg",
            "high",
            ingress_cidr="0.0.0.0/0",
        ),
        kit.node(
            _SINK,
            NodeType.RDS_INSTANCE,
            "customer-financials-db",
            "critical",
            publicly_accessible="true",
        ),
        kit.node(
            "s3-financials-archive", NodeType.S3_BUCKET, "customer-financials-archive", "high"
        ),
        kit.node(
            "data-customer-financials",
            NodeType.DATASET,
            "customer-financial-transactions",
            "critical",
            classification="restricted",
        ),
    ]


def _edges(kit: Kit) -> list[GraphEdge]:
    return [
        kit.edge(_ENTRY, _SINK, EdgeType.EXPOSED_TO_INTERNET, "critical"),
        kit.edge(_SINK, "sg-rds-public", EdgeType.HAS_SECURITY_GROUP, "high"),
        kit.edge(
            "s3-financials-archive",
            "data-customer-financials",
            EdgeType.STORES_SENSITIVE_DATA,
            "none",
        ),
    ]


def _findings(kit: Kit) -> list[ExpectedFinding]:
    return [
        ExpectedFinding(
            id=kit.nid("finding-rds-instance-public-01"),
            severity="critical",
            family=FindingFamily.RDS_INSTANCE_PUBLIC,
            resource_ids=[kit.nid(_SINK)],
            expected_scanner_visibility="visible",
            ground_truth="RDS database is publicly accessible and reachable from the internet",
            remediation="Set publicly_accessible = false and isolate database in private subnets",
        ),
    ]


def _critical(kit: Kit) -> GroundTruthPath:
    return GroundTruthPath(
        id=kit.nid("path-critical-rds-01"),
        severity="critical",
        nodes=[kit.nid(_ENTRY), kit.nid(_SINK)],
        edges=[kit.ek(_ENTRY, EdgeType.EXPOSED_TO_INTERNET, _SINK)],
        sink_kind=SinkKind.DATABASE,
        target=kit.nid(_SINK),
        explanation=(
            "customer-financials-db is publicly accessible behind a 0.0.0.0/0 "
            "security group, so the database listener is reachable from the internet"
        ),
    )
