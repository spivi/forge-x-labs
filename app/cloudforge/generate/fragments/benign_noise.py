"""Benign noise fragments — diverse filler pool for graph scale.

Adds non-risky, uninteresting cloud resources (S3 buckets, SQS queues, KMS keys,
IAM roles, datasets, log trails, ECR repositories) with no findings, no edges,
and no ground-truth paths to vary background topology and scale budgets.
"""

from __future__ import annotations

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


def _tags(rng: Random) -> NodeTags:
    return NodeTags(
        env=rng.choice(ENV_VALUES), owner=rng.choice(OWNER_VALUES), app=rng.choice(APP_VALUES)
    )


def _bundle(node: GraphNode) -> FragmentBundle:
    return FragmentBundle(nodes=[node], edges=[], findings=[], paths=[])


@register("benign_noise.unrelated_bucket")
class BenignNoiseUnrelatedBucket:
    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        return _bundle(
            GraphNode(
                id=f"{ns}/s3-noise",
                type=NodeType.S3_BUCKET,
                name=rng.choice(BUCKET_NAMES),
                tags=_tags(rng),
                security=NodeSecurity(criticality="low"),
            )
        )


@register("benign_noise.sqs_queue")
class BenignNoiseSqsQueue:
    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        return _bundle(
            GraphNode(
                id=f"{ns}/sqs-noise",
                type=NodeType.SQS_QUEUE,
                name=rng.choice(QUEUE_NAMES),
                tags=_tags(rng),
                security=NodeSecurity(criticality="low"),
                attributes={"visibility_timeout_seconds": "30"},
            )
        )


@register("benign_noise.kms_key")
class BenignNoiseKmsKey:
    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        return _bundle(
            GraphNode(
                id=f"{ns}/kms-noise",
                type=NodeType.KMS_KEY,
                name=rng.choice(KMS_NAMES),
                tags=_tags(rng),
                security=NodeSecurity(criticality="low"),
                attributes={"description": "internal storage key"},
            )
        )


@register("benign_noise.iam_role")
class BenignNoiseIamRole:
    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        return _bundle(
            GraphNode(
                id=f"{ns}/role-noise",
                type=NodeType.IAM_ROLE,
                name=rng.choice(ROLE_NAMES),
                tags=_tags(rng),
                security=NodeSecurity(criticality="low"),
                attributes={"principal_service": "ec2.amazonaws.com"},
            )
        )


@register("benign_noise.ecr_repo")
class BenignNoiseEcrRepo:
    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        return _bundle(
            GraphNode(
                id=f"{ns}/ecr-noise",
                type=NodeType.ECR_REPOSITORY,
                name=rng.choice(ECR_NAMES),
                tags=_tags(rng),
                security=NodeSecurity(criticality="low"),
                attributes={"image_tag_mutability": "MUTABLE"},
            )
        )


@register("benign_noise.data_set")
class BenignNoiseDataSet:
    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        return _bundle(
            GraphNode(
                id=f"{ns}/data-noise",
                type=NodeType.DATASET,
                name=rng.choice(DATA_NAMES),
                tags=_tags(rng),
                security=NodeSecurity(criticality="low"),
                attributes={"classification": "internal"},
            )
        )


@register("benign_noise.log_trail")
class BenignNoiseLogTrail:
    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        return _bundle(
            GraphNode(
                id=f"{ns}/trail-noise",
                type=NodeType.LOG_TRAIL,
                name=rng.choice(TRAIL_NAMES),
                tags=_tags(rng),
                security=NodeSecurity(criticality="low"),
            )
        )
