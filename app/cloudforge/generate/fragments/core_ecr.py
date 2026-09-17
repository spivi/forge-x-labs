"""``core.ecr_repository_public_read``: a public container image repository.

What the attacker reaches is the repository (``sink_kind`` ``image``): the
image and whatever it embeds. The proprietary source the image was built from
also lives in a private archive bucket, off the graded path.

Difficulty adds, through the composer's shape: a public-looking bucket the
account exposes that a policy locks down (``dead_end``), a lookalike repository
with the same wildcard pull policy behind an org-scoped condition
(``lookalike``), and an application identity route to the same repository
(``prefix_hops``), labeled as its own high-severity path.
"""

from __future__ import annotations

from random import Random
from typing import Any

from app.cloudforge.generate.fragments import _aws_shape as aws
from app.cloudforge.generate.fragments._core import Kit, Piece, shape_of
from app.cloudforge.generate.fragments._vocab import LOOKALIKE_REPOSITORIES
from app.cloudforge.generate.fragments.base import FragmentBundle, register_core
from app.cloudforge.models.findings import (
    ExpectedFinding,
    FindingFamily,
    GroundTruthPath,
    SinkKind,
)
from app.cloudforge.models.graph import EdgeType, GraphEdge, GraphNode, NodeTags, NodeType

_TAGS = NodeTags(env="prod", owner="container-platform", app="payment-gateway")
_ENTRY = "acct-main"
_SINK = "ecr-payment-gateway"
_ACTIONS = ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"]


@register_core
class EcrRepositoryPublicRead:
    scenario_type = "ecr_repository_public_read"
    cloud = "aws"
    prompt = (
        "A container repository hosts application images. Can external parties "
        "pull the image, and what does it embed?"
    )
    checklist = ("ecr_repository_public_read", "Containers: Public Read ECR Repository Policy")
    teaching_point = "Public registry; reaches the image and what it embeds"

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
        sink_kind=SinkKind.IMAGE,
        stem="ecr",
        dead_end=aws.dead_end_bucket,
    )


def _lookalike(kit: Kit, rng: Random) -> Piece:
    return aws.lookalike(
        kit,
        rng,
        _ENTRY,
        EdgeType.EXPOSED_TO_INTERNET,
        "ecr",
        NodeType.ECR_REPOSITORY,
        LOOKALIKE_REPOSITORIES,
        **aws.conditioned(principal="*", actions=list(_ACTIONS)),
    )


def _nodes(kit: Kit) -> list[GraphNode]:
    return [
        kit.node(_ENTRY, NodeType.ACCOUNT, "prod-account", "medium"),
        kit.node(
            _SINK,
            NodeType.ECR_REPOSITORY,
            "payment-gateway-service",
            "critical",
            principal="*",
            actions=list(_ACTIONS),
        ),
        kit.node(
            "s3-source-archive", NodeType.S3_BUCKET, "payment-gateway-source-archive", "high"
        ),
        kit.node(
            "data-proprietary-source",
            NodeType.DATASET,
            "proprietary-payment-gateway-code",
            "critical",
            classification="restricted",
        ),
    ]


def _edges(kit: Kit) -> list[GraphEdge]:
    return [
        kit.edge(_ENTRY, _SINK, EdgeType.EXPOSED_TO_INTERNET, "critical"),
        kit.edge(
            "s3-source-archive",
            "data-proprietary-source",
            EdgeType.STORES_SENSITIVE_DATA,
            "none",
        ),
    ]


def _findings(kit: Kit) -> list[ExpectedFinding]:
    return [
        ExpectedFinding(
            id=kit.nid("finding-ecr-repo-public-read-01"),
            severity="critical",
            family=FindingFamily.ECR_REPOSITORY_PUBLIC_READ,
            resource_ids=[kit.nid(_SINK)],
            expected_scanner_visibility="visible",
            ground_truth="ECR container repository policy allows public pull permissions",
            remediation=(
                "Remove wildcard principal from ECR repository policy and "
                "require authenticated IAM access"
            ),
        ),
    ]


def _critical(kit: Kit) -> GroundTruthPath:
    return GroundTruthPath(
        id=kit.nid("path-critical-ecr-01"),
        severity="critical",
        nodes=[kit.nid(_ENTRY), kit.nid(_SINK)],
        edges=[kit.ek(_ENTRY, EdgeType.EXPOSED_TO_INTERNET, _SINK)],
        sink_kind=SinkKind.IMAGE,
        target=kit.nid(_SINK),
        explanation=(
            "The payment-gateway-service repository policy grants pull to *, so anyone "
            "can extract the image and whatever the layers embed"
        ),
    )
