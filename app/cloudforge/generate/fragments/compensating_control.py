"""``compensating_control.explicit_deny`` fragment — pure control infrastructure.

Story: a bucket wired to a log trail via an explicit ``logs_to`` edge. This
fragment owns only the control itself (the trail node + the logging edge) —
no finding is generated, because a working compensating control is not a risk
to report on. Composed alongside a risky fragment, it can neutralize what
would otherwise be a "missing logging" finding.
"""

from __future__ import annotations

from random import Random
from typing import Any

from app.cloudforge.generate.fragments._vocab import APP_VALUES, ENV_VALUES, OWNER_VALUES
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
        bucket = GraphNode(
            id=f"{ns}/s3-controlled",
            type=NodeType.S3_BUCKET,
            name="controlled-bucket",
            tags=tags,
            security=NodeSecurity(criticality="low"),
        )
        trail = GraphNode(
            id=f"{ns}/trail-control",
            type=NodeType.LOG_TRAIL,
            name="control-trail",
            tags=tags,
            security=NodeSecurity(criticality="low"),
        )
        logs_to = GraphEdge(
            from_=f"{ns}/s3-controlled",
            to=f"{ns}/trail-control",
            type=EdgeType.LOGS_TO,
            security=EdgeSecurity(risk="none"),
        )
        return FragmentBundle(nodes=[bucket, trail], edges=[logs_to], findings=[], paths=[])
