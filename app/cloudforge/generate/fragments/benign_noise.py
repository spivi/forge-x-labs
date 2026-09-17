"""Benign noise fragments — diverse filler pool for graph scale.

Adds non-risky, uninteresting cloud resources (S3 buckets, SQS queues, KMS keys,
IAM roles, datasets, log trails, ECR repositories) with no findings, no edges,
and no ground-truth paths to vary background topology and scale budgets.

Each node's id slug is derived from the vocabulary name it draws (``s3-telemetry-logs``,
``role-backup-runner``), the same shape the core fragments use, so neither the id
nor the name says the node is filler. The composer marks that in ``GraphNode.origin``.
"""

from __future__ import annotations

import re
from random import Random
from typing import Any

from app.cloudforge.generate.fragments._vocab import (
    APP_VALUES,
    BUCKET_NAMES,
    DATA_NAMES,
    ECR_NAMES,
    ENV_VALUES,
    KMS_NAMES,
    OWNER_VALUES,
    QUEUE_NAMES,
    ROLE_NAMES,
    TRAIL_NAMES,
)
from app.cloudforge.generate.fragments.base import FragmentBundle, register
from app.cloudforge.models.graph import GraphNode, NodeSecurity, NodeTags, NodeType

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_TYPE_PREFIXES = ("kms-", "trail-", "data-", "repo-")


def _tags(rng: Random) -> NodeTags:
    return NodeTags(
        env=rng.choice(ENV_VALUES), owner=rng.choice(OWNER_VALUES), app=rng.choice(APP_VALUES)
    )


def _bundle(node: GraphNode) -> FragmentBundle:
    return FragmentBundle(nodes=[node], edges=[], findings=[], paths=[])


def _slug(prefix: str, name: str) -> str:
    """``("s3", "telemetry-logs")`` -> ``s3-telemetry-logs``;
    ``("role", "BackupRunnerRole")`` -> ``role-backup-runner``;
    ``("kms", "kms-app-configs")`` -> ``kms-app-configs``."""
    stem = _CAMEL_BOUNDARY.sub("-", name).lower().removesuffix("-role")
    for known in _TYPE_PREFIXES:
        stem = stem.removeprefix(known)
    return f"{prefix}-{stem}"


@register("benign_noise.unrelated_bucket")
class BenignNoiseUnrelatedBucket:
    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        name = rng.choice(BUCKET_NAMES)
        return _bundle(
            GraphNode(
                id=f"{ns}/{_slug('s3', name)}",
                type=NodeType.S3_BUCKET,
                name=name,
                tags=_tags(rng),
                security=NodeSecurity(criticality="low"),
            )
        )


@register("benign_noise.sqs_queue")
class BenignNoiseSqsQueue:
    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        name = rng.choice(QUEUE_NAMES)
        return _bundle(
            GraphNode(
                id=f"{ns}/{_slug('sqs', name)}",
                type=NodeType.SQS_QUEUE,
                name=name,
                tags=_tags(rng),
                security=NodeSecurity(criticality="low"),
                attributes={"visibility_timeout_seconds": "30"},
            )
        )


@register("benign_noise.kms_key")
class BenignNoiseKmsKey:
    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        name = rng.choice(KMS_NAMES)
        return _bundle(
            GraphNode(
                id=f"{ns}/{_slug('kms', name)}",
                type=NodeType.KMS_KEY,
                name=name,
                tags=_tags(rng),
                security=NodeSecurity(criticality="low"),
                attributes={"description": "internal storage key"},
            )
        )


@register("benign_noise.iam_role")
class BenignNoiseIamRole:
    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        name = rng.choice(ROLE_NAMES)
        return _bundle(
            GraphNode(
                id=f"{ns}/{_slug('role', name)}",
                type=NodeType.IAM_ROLE,
                name=name,
                tags=_tags(rng),
                security=NodeSecurity(criticality="low"),
                attributes={"principal_service": "ec2.amazonaws.com"},
            )
        )


@register("benign_noise.ecr_repo")
class BenignNoiseEcrRepo:
    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        name = rng.choice(ECR_NAMES)
        return _bundle(
            GraphNode(
                id=f"{ns}/{_slug('ecr', name)}",
                type=NodeType.ECR_REPOSITORY,
                name=name,
                tags=_tags(rng),
                security=NodeSecurity(criticality="low"),
                attributes={"image_tag_mutability": "MUTABLE"},
            )
        )


@register("benign_noise.data_set")
class BenignNoiseDataSet:
    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        name = rng.choice(DATA_NAMES)
        return _bundle(
            GraphNode(
                id=f"{ns}/{_slug('data', name)}",
                type=NodeType.DATASET,
                name=name,
                tags=_tags(rng),
                security=NodeSecurity(criticality="low"),
                attributes={"classification": "internal"},
            )
        )


@register("benign_noise.log_trail")
class BenignNoiseLogTrail:
    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        name = rng.choice(TRAIL_NAMES)
        return _bundle(
            GraphNode(
                id=f"{ns}/{_slug('trail', name)}",
                type=NodeType.LOG_TRAIL,
                name=name,
                tags=_tags(rng),
                security=NodeSecurity(criticality="low"),
            )
        )
