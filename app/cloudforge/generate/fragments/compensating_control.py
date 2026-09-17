"""``compensating_control.explicit_deny`` fragment: pure control infrastructure.

Story: a bucket wired to a log trail via an explicit ``logs_to`` edge, holding a
``restricted`` data set that no identity in the estate can reach. This fragment
owns only the control and what it guards (the trail node, the logging edge, the
data set); no finding is generated, because a working compensating control is
not a risk to report on. Composed alongside a risky fragment, it can neutralize
what would otherwise be a "missing logging" finding, and its restricted data set
means the core sink is never the only restricted data on the board.

Ids and names come from ``_vocab.LOGGED_BUCKETS`` and read like an ordinary
bucket with its own access-log trail; nothing in them says "control".
"""

from __future__ import annotations

from random import Random
from typing import Any

from app.cloudforge.generate.fragments._vocab import (
    APP_VALUES,
    ENV_VALUES,
    LOGGED_BUCKETS,
    OWNER_VALUES,
    SINK_CLASSIFICATION,
)
from app.cloudforge.generate.fragments.base import FragmentBundle, register
from app.cloudforge.models.graph import (
    EdgeSecurity,
    EdgeType,
    GraphEdge,
    GraphNode,
    NodeSecurity,
    NodeTags,
    NodeType,
)


@register("compensating_control.explicit_deny")
class CompensatingControlExplicitDeny:
    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        tags = NodeTags(
            env=rng.choice(ENV_VALUES), owner=rng.choice(OWNER_VALUES), app=rng.choice(APP_VALUES)
        )
        stem, bucket_name, trail_name, data_name = rng.choice(LOGGED_BUCKETS)
        bucket_id = f"{ns}/s3-{stem}"
        trail_id = f"{ns}/trail-{stem}"
        data_id = f"{ns}/data-{stem}"
        bucket = GraphNode(
            id=bucket_id,
            type=NodeType.S3_BUCKET,
            name=bucket_name,
            tags=tags,
            security=NodeSecurity(criticality="low"),
        )
        trail = GraphNode(
            id=trail_id,
            type=NodeType.LOG_TRAIL,
            name=trail_name,
            tags=tags,
            security=NodeSecurity(criticality="low"),
        )
        data = GraphNode(
            id=data_id,
            type=NodeType.DATASET,
            name=data_name,
            tags=tags,
            security=NodeSecurity(criticality="medium"),
            attributes={"classification": SINK_CLASSIFICATION},
        )
        logs_to = GraphEdge(
            from_=bucket_id,
            to=trail_id,
            type=EdgeType.LOGS_TO,
            security=EdgeSecurity(risk="none"),
        )
        holds = GraphEdge(
            from_=bucket_id,
            to=data_id,
            type=EdgeType.STORES_SENSITIVE_DATA,
            security=EdgeSecurity(risk="none"),
        )
        return FragmentBundle(
            nodes=[bucket, trail, data], edges=[logs_to, holds], findings=[], paths=[]
        )
