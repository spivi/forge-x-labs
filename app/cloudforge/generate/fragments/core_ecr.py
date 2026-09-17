"""``core.ecr_repository_public_read`` — Public container image repository."""

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

_TAGS = NodeTags(env="prod", owner="container-platform", app="payment-gateway")


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


@register("core.ecr_repository_public_read")
class EcrRepositoryPublicRead:
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
            "ecr-payment-gateway",
            NodeType.ECR_REPOSITORY,
            "payment-gateway-service",
            "critical",
            principal="*",
            actions=["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"],
        ),
        _node(
            ns,
            "data-proprietary-source",
            NodeType.DATASET,
            "ProprietaryPaymentGatewayCode",
            "critical",
            classification="restricted",
        ),
    ]


def _edges(ns: str) -> list[GraphEdge]:
    return [
        _edge(ns, "acct-main", "ecr-payment-gateway", EdgeType.EXPOSED_TO_INTERNET, "critical"),
        _edge(
            ns,
            "ecr-payment-gateway",
            "data-proprietary-source",
            EdgeType.STORES_SENSITIVE_DATA,
            "none",
        ),
    ]


def _findings(ns: str) -> list[ExpectedFinding]:
    return [
        ExpectedFinding(
            id=_nid(ns, "finding-ecr-repo-public-read-01"),
            severity="critical",
            family=FindingFamily.ECR_REPOSITORY_PUBLIC_READ,
            resource_ids=[_nid(ns, "ecr-payment-gateway")],
            expected_scanner_visibility="visible",
            ground_truth="ECR container repository policy allows public pull permissions",
            remediation=(
                "Remove wildcard principal from ECR repository policy and "
                "require authenticated IAM access"
            ),
        ),
    ]


def _ek(ns: str, src: str, edge_type: EdgeType, dst: str) -> str:
    return f"{_nid(ns, src)}->{edge_type.value}->{_nid(ns, dst)}"


def _critical(ns: str) -> GroundTruthPath:
    return GroundTruthPath(
        id=_nid(ns, "path-critical-ecr-01"),
        severity="critical",
        nodes=[
            _nid(ns, "acct-main"),
            _nid(ns, "ecr-payment-gateway"),
            _nid(ns, "data-proprietary-source"),
        ],
        edges=[
            _ek(ns, "acct-main", EdgeType.EXPOSED_TO_INTERNET, "ecr-payment-gateway"),
            _ek(
                ns,
                "ecr-payment-gateway",
                EdgeType.STORES_SENSITIVE_DATA,
                "data-proprietary-source",
            ),
        ],
        explanation=(
            "Public container repository policy allows unauthenticated extraction "
            "of proprietary payment gateway code"
        ),
    )
