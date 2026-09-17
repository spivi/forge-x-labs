"""``core.sqs_queue_overbroad_policy`` — Publicly accessible SQS queue."""

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

_TAGS = NodeTags(env="prod", owner="messaging-team", app="event-bus")


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


@register("core.sqs_queue_overbroad_policy")
class SqsQueueOverbroadPolicy:
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
            "sqs-order-events",
            NodeType.SQS_QUEUE,
            "order-events-queue",
            "critical",
            principal="*",
            actions=["sqs:ReceiveMessage", "sqs:SendMessage"],
        ),
        _node(
            ns,
            "data-order-events",
            NodeType.DATASET,
            "OrderTransactionPayloads",
            "critical",
            classification="restricted",
        ),
    ]


def _edges(ns: str) -> list[GraphEdge]:
    return [
        _edge(ns, "acct-main", "sqs-order-events", EdgeType.EXPOSED_TO_INTERNET, "critical"),
        _edge(
            ns,
            "sqs-order-events",
            "data-order-events",
            EdgeType.STORES_SENSITIVE_DATA,
            "none",
        ),
    ]


def _findings(ns: str) -> list[ExpectedFinding]:
    return [
        ExpectedFinding(
            id=_nid(ns, "finding-sqs-queue-policy-overbroad-01"),
            severity="critical",
            family=FindingFamily.SQS_QUEUE_POLICY_OVERBROAD,
            resource_ids=[_nid(ns, "sqs-order-events")],
            expected_scanner_visibility="visible",
            ground_truth="SQS queue policy allows wildcard principal to receive and send messages",
            remediation=(
                "Restrict SQS queue access policy to explicit producer and consumer IAM roles"
            ),
        ),
    ]


def _ek(ns: str, src: str, edge_type: EdgeType, dst: str) -> str:
    return f"{_nid(ns, src)}->{edge_type.value}->{_nid(ns, dst)}"


def _critical(ns: str) -> GroundTruthPath:
    return GroundTruthPath(
        id=_nid(ns, "path-critical-sqs-01"),
        severity="critical",
        nodes=[
            _nid(ns, "acct-main"),
            _nid(ns, "sqs-order-events"),
            _nid(ns, "data-order-events"),
        ],
        edges=[
            _ek(ns, "acct-main", EdgeType.EXPOSED_TO_INTERNET, "sqs-order-events"),
            _ek(ns, "sqs-order-events", EdgeType.STORES_SENSITIVE_DATA, "data-order-events"),
        ],
        explanation=(
            "Wildcard queue policy allows external parties to consume "
            "confidential order transaction payloads"
        ),
    )
