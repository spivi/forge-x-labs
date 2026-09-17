"""``core.lambda_public_function_url`` — Unauthenticated Lambda Function URL."""

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

_TAGS = NodeTags(env="prod", owner="serverless-team", app="ecommerce-api")


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


@register("core.lambda_public_function_url")
class LambdaPublicFunctionUrl:
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
            "lambda-order-lookup",
            NodeType.LAMBDA_FUNCTION,
            "order-lookup-service",
            "critical",
            auth_type="NONE",
        ),
        _node(ns, "role-lambda-exec", NodeType.IAM_ROLE, "OrderLookupLambdaRole", "high"),
        _node(
            ns,
            "pol-lambda-s3",
            NodeType.IAM_POLICY,
            "OrderLookupDataPolicy",
            "high",
            actions=["s3:Get*", "s3:List*"],
        ),
        _node(
            ns,
            "s3-customer-orders",
            NodeType.S3_BUCKET,
            "customer-orders-prod-000000000000",
            "critical",
        ),
        _node(
            ns,
            "data-customer-orders",
            NodeType.DATASET,
            "customer-order-history",
            "critical",
            classification="restricted",
        ),
    ]


def _edges(ns: str) -> list[GraphEdge]:
    return [
        _edge(ns, "acct-main", "lambda-order-lookup", EdgeType.EXPOSED_TO_INTERNET, "critical"),
        _edge(ns, "lambda-order-lookup", "role-lambda-exec", EdgeType.ASSUMES, "critical"),
        _edge(ns, "role-lambda-exec", "pol-lambda-s3", EdgeType.ATTACHED_POLICY, "high"),
        _edge(ns, "role-lambda-exec", "s3-customer-orders", EdgeType.CAN_READ, "critical"),
        _edge(
            ns,
            "s3-customer-orders",
            "data-customer-orders",
            EdgeType.STORES_SENSITIVE_DATA,
            "none",
        ),
    ]


def _findings(ns: str) -> list[ExpectedFinding]:
    return [
        ExpectedFinding(
            id=_nid(ns, "finding-lambda-url-unauthenticated-01"),
            severity="critical",
            family=FindingFamily.LAMBDA_FUNCTION_URL_UNAUTHENTICATED,
            resource_ids=[_nid(ns, "lambda-order-lookup")],
            expected_scanner_visibility="visible",
            ground_truth=(
                "Lambda Function URL configured with authorization_type = 'NONE' "
                "allows public unauthenticated invocation"
            ),
            remediation=(
                "Change Function URL authorization_type to AWS_IAM or front with "
                "an authenticated API Gateway"
            ),
        ),
        ExpectedFinding(
            id=_nid(ns, "finding-iam-excessive-privilege-01"),
            severity="high",
            family=FindingFamily.IAM_EXCESSIVE_PRIVILEGE,
            resource_ids=[_nid(ns, "role-lambda-exec"), _nid(ns, "pol-lambda-s3")],
            expected_scanner_visibility="visible",
            ground_truth="Lambda execution role holds broad s3:Get* permissions on orders",
            remediation="Scope IAM policy to specific S3 object prefixes",
        ),
    ]


def _ek(ns: str, src: str, edge_type: EdgeType, dst: str) -> str:
    return f"{_nid(ns, src)}->{edge_type.value}->{_nid(ns, dst)}"


def _critical(ns: str) -> GroundTruthPath:
    return GroundTruthPath(
        id=_nid(ns, "path-critical-lambda-01"),
        severity="critical",
        nodes=[
            _nid(ns, "lambda-order-lookup"),
            _nid(ns, "role-lambda-exec"),
            _nid(ns, "s3-customer-orders"),
            _nid(ns, "data-customer-orders"),
        ],
        edges=[
            _ek(ns, "lambda-order-lookup", EdgeType.ASSUMES, "role-lambda-exec"),
            _ek(ns, "role-lambda-exec", EdgeType.CAN_READ, "s3-customer-orders"),
            _ek(ns, "s3-customer-orders", EdgeType.STORES_SENSITIVE_DATA, "data-customer-orders"),
        ],
        explanation=(
            "Public unauthenticated Lambda Function URL proxies "
            "directly to sensitive customer order history"
        ),
    )
