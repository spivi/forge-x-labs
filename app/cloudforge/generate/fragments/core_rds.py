"""``core.public_rds_instance``: a publicly accessible RDS database.

What the attacker reaches is the database itself (``sink_kind`` ``database``):
it is routable from the internet behind a 0.0.0.0/0 security group. The
financial transactions it serves also sit in a private archive bucket, off the
graded path, so the estate's data sets do not point at the exposed instance.
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

_TAGS = NodeTags(env="prod", owner="database-team", app="billing-core")


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


@register("core.public_rds_instance")
class PublicRdsInstance:
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
        _node(
            ns,
            "sg-rds-public",
            NodeType.SECURITY_GROUP,
            "public-db-sg",
            "high",
            ingress_cidr="0.0.0.0/0",
        ),
        _node(
            ns,
            "rds-customer-db",
            NodeType.RDS_INSTANCE,
            "customer-financials-db",
            "critical",
            publicly_accessible="true",
        ),
        _node(
            ns,
            "s3-financials-archive",
            NodeType.S3_BUCKET,
            "customer-financials-archive",
            "high",
        ),
        _node(
            ns,
            "data-customer-financials",
            NodeType.DATASET,
            "customer-financial-transactions",
            "critical",
            classification="restricted",
        ),
    ]


def _edges(ns: str) -> list[GraphEdge]:
    return [
        _edge(ns, "acct-main", "rds-customer-db", EdgeType.EXPOSED_TO_INTERNET, "critical"),
        _edge(ns, "rds-customer-db", "sg-rds-public", EdgeType.HAS_SECURITY_GROUP, "high"),
        _edge(
            ns,
            "s3-financials-archive",
            "data-customer-financials",
            EdgeType.STORES_SENSITIVE_DATA,
            "none",
        ),
    ]


def _findings(ns: str) -> list[ExpectedFinding]:
    return [
        ExpectedFinding(
            id=_nid(ns, "finding-rds-instance-public-01"),
            severity="critical",
            family=FindingFamily.RDS_INSTANCE_PUBLIC,
            resource_ids=[_nid(ns, "rds-customer-db")],
            expected_scanner_visibility="visible",
            ground_truth="RDS database is publicly accessible and reachable from the internet",
            remediation="Set publicly_accessible = false and isolate database in private subnets",
        ),
    ]


def _ek(ns: str, src: str, edge_type: EdgeType, dst: str) -> str:
    return f"{_nid(ns, src)}->{edge_type.value}->{_nid(ns, dst)}"


def _critical(ns: str) -> GroundTruthPath:
    return GroundTruthPath(
        id=_nid(ns, "path-critical-rds-01"),
        severity="critical",
        nodes=[_nid(ns, "acct-main"), _nid(ns, "rds-customer-db")],
        edges=[_ek(ns, "acct-main", EdgeType.EXPOSED_TO_INTERNET, "rds-customer-db")],
        sink_kind=SinkKind.DATABASE,
        target=_nid(ns, "rds-customer-db"),
        explanation=(
            "customer-financials-db is publicly accessible behind a 0.0.0.0/0 "
            "security group, so the database listener is reachable from the internet"
        ),
    )
