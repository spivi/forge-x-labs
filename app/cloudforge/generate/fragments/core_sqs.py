"""``core.sqs_queue_overbroad_policy``: a queue policy open to any principal.

What the attacker reaches is the queue (``sink_kind`` ``queue``): the messages
in flight, readable and writable by anyone. The transaction payloads the queue
carries also land in a private archive bucket, off the graded path.

Difficulty adds, through the composer's shape: a public-looking bucket the
account exposes that a policy locks down (``dead_end``), a lookalike queue with
the same wildcard policy behind an org-scoped condition (``lookalike``), and an
application identity route to the same queue (``prefix_hops``), labeled as its
own high-severity path.
"""

from __future__ import annotations

from random import Random
from typing import Any

from app.cloudforge.generate.fragments import _aws_shape as aws
from app.cloudforge.generate.fragments._core import Kit, Piece, shape_of
from app.cloudforge.generate.fragments._vocab import LOOKALIKE_QUEUES
from app.cloudforge.generate.fragments.base import FragmentBundle, register
from app.cloudforge.models.findings import (
    ExpectedFinding,
    FindingFamily,
    GroundTruthPath,
    SinkKind,
)
from app.cloudforge.models.graph import EdgeType, GraphEdge, GraphNode, NodeTags, NodeType

_TAGS = NodeTags(env="prod", owner="messaging-team", app="event-bus")
_ENTRY = "acct-main"
_SINK = "sqs-order-events"
_ACTIONS = ["sqs:ReceiveMessage", "sqs:SendMessage"]


@register("core.sqs_queue_overbroad_policy")
class SqsQueueOverbroadPolicy:
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
        actions=list(_ACTIONS),
        sink_kind=SinkKind.QUEUE,
        stem="sqs",
        dead_end=aws.dead_end_bucket,
    )


def _lookalike(kit: Kit, rng: Random) -> Piece:
    return aws.lookalike(
        kit,
        rng,
        _ENTRY,
        EdgeType.EXPOSED_TO_INTERNET,
        "sqs",
        NodeType.SQS_QUEUE,
        LOOKALIKE_QUEUES,
        **aws.conditioned(principal="*", actions=list(_ACTIONS)),
    )


def _nodes(kit: Kit) -> list[GraphNode]:
    return [
        kit.node(_ENTRY, NodeType.ACCOUNT, "prod-account", "medium"),
        kit.node(
            _SINK,
            NodeType.SQS_QUEUE,
            "order-events-queue",
            "critical",
            principal="*",
            actions=list(_ACTIONS),
        ),
        kit.node("s3-order-archive", NodeType.S3_BUCKET, "order-events-archive", "high"),
        kit.node(
            "data-order-events",
            NodeType.DATASET,
            "order-transaction-payloads",
            "critical",
            classification="restricted",
        ),
    ]


def _edges(kit: Kit) -> list[GraphEdge]:
    return [
        kit.edge(_ENTRY, _SINK, EdgeType.EXPOSED_TO_INTERNET, "critical"),
        kit.edge("s3-order-archive", "data-order-events", EdgeType.STORES_SENSITIVE_DATA, "none"),
    ]


def _findings(kit: Kit) -> list[ExpectedFinding]:
    return [
        ExpectedFinding(
            id=kit.nid("finding-sqs-queue-policy-overbroad-01"),
            severity="critical",
            family=FindingFamily.SQS_QUEUE_POLICY_OVERBROAD,
            resource_ids=[kit.nid(_SINK)],
            expected_scanner_visibility="visible",
            ground_truth="SQS queue policy allows wildcard principal to receive and send messages",
            remediation=(
                "Restrict SQS queue access policy to explicit producer and consumer IAM roles"
            ),
        ),
    ]


def _critical(kit: Kit) -> GroundTruthPath:
    return GroundTruthPath(
        id=kit.nid("path-critical-sqs-01"),
        severity="critical",
        nodes=[kit.nid(_ENTRY), kit.nid(_SINK)],
        edges=[kit.ek(_ENTRY, EdgeType.EXPOSED_TO_INTERNET, _SINK)],
        sink_kind=SinkKind.QUEUE,
        target=kit.nid(_SINK),
        explanation=(
            "The order-events-queue policy grants sqs:ReceiveMessage and "
            "sqs:SendMessage to *, so any party can consume or inject the "
            "transaction messages in flight"
        ),
    )
