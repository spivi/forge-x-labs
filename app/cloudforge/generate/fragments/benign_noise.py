"""``benign_noise.unrelated_bucket`` fragment — pure filler for graph scale.

Story: one unrelated, uninteresting S3 bucket with no risky attributes, no
edges, no findings, no ground-truth paths. Its only job is to add bulk toward
a scale profile's node budget without affecting scenario semantics.
"""

from __future__ import annotations

from random import Random
from typing import Any

from app.cloudforge.generate.fragments._vocab import APP_VALUES, ENV_VALUES, OWNER_VALUES
from app.cloudforge.generate.fragments.base import FragmentBundle, register
from app.cloudforge.models.graph import GraphNode, NodeSecurity, NodeTags, NodeType


@register("benign_noise.unrelated_bucket")
class BenignNoiseUnrelatedBucket:
    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        tags = NodeTags(
            env=rng.choice(ENV_VALUES), owner=rng.choice(OWNER_VALUES), app=rng.choice(APP_VALUES)
        )
        bucket = GraphNode(
            id=f"{ns}/s3-noise",
            type=NodeType.S3_BUCKET,
            name="unrelated-bucket",
            tags=tags,
            security=NodeSecurity(criticality="low"),
        )
        return FragmentBundle(nodes=[bucket], edges=[], findings=[], paths=[])
