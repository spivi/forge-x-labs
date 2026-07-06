"""``false_positive.public_denied_bucket`` fragment — a benign false-positive.

Story: a bucket that *looks* public (public-access attribute set) but is
protected by an explicit compensating control (a bucket policy that denies
anonymous access). Mirrors the ``s3-public-assets``/``s3-locked-backups``
false-positive pattern in the core fragments — a scanner naively flagging
"public access enabled" would be wrong; the ground truth here is benign.
"""

from __future__ import annotations

from random import Random
from typing import Any

from app.cloudforge.generate.fragments._vocab import APP_VALUES, ENV_VALUES, OWNER_VALUES
from app.cloudforge.generate.fragments.base import FragmentBundle, register
from app.cloudforge.models.findings import ExpectedFinding, FindingFamily
from app.cloudforge.models.graph import GraphNode, NodeSecurity, NodeTags, NodeType


@register("false_positive.public_denied_bucket")
class FalsePositivePublicDeniedBucket:
    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        tags = NodeTags(
            env=rng.choice(ENV_VALUES), owner=rng.choice(OWNER_VALUES), app=rng.choice(APP_VALUES)
        )
        bucket = GraphNode(
            id=f"{ns}/s3-public-denied",
            type=NodeType.S3_BUCKET,
            name="public-looking-denied",
            tags=tags,
            security=NodeSecurity(criticality="low"),
            attributes={"public_access": "enabled", "compensating_control": "true"},
        )
        finding = ExpectedFinding(
            id=f"{ns}/find-fp-01",
            severity="low",
            family=FindingFamily.PUBLIC_LOOKING_BUCKET_WITH_COMPENSATING_CONTROL,
            resource_ids=[f"{ns}/s3-public-denied"],
            expected_scanner_visibility="visible",
            ground_truth="benign",
            remediation=(
                "None needed — an explicit-deny bucket policy blocks anonymous access "
                "despite the public-looking attribute."
            ),
        )
        return FragmentBundle(nodes=[bucket], edges=[], findings=[finding], paths=[])
