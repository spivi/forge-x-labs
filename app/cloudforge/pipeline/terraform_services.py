"""Container registry and messaging services HCL blocks (FXL-154)."""

from __future__ import annotations

import json

from app.cloudforge import constants
from app.cloudforge.models.graph import GraphNode, NodeType
from app.cloudforge.pipeline.identifiers import resource_name
from app.cloudforge.pipeline.terraform_resource_blocks import hcl_str, neutralize_hcl_openers

_EMPTY = constants.EMPTY_TF_HEADER
_STAR = "*"


def ecr_repository_block(node: GraphNode) -> str:
    """An ``aws_ecr_repository`` and optional repository access policy."""
    ref = resource_name(node)
    principal = str(node.attributes.get("principal", _STAR))
    actions = node.attributes.get("actions") or [
        "ecr:BatchGetImage",
        "ecr:GetDownloadUrlForLayer",
    ]
    if not isinstance(actions, list):
        actions = [str(actions)]
    actions = [neutralize_hcl_openers(str(a)) for a in actions]

    blocks = [
        f'resource "aws_ecr_repository" "{ref}" {{',
        f"  name                 = {hcl_str(node.name)}",
        '  image_tag_mutability = "MUTABLE"',
        "  tags                 = local.common_tags",
        "}",
    ]
    document = json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "RepoPolicy",
                    "Effect": "Allow",
                    "Principal": (
                        _STAR if principal == _STAR else {"AWS": f"arn:aws:iam::{principal}:root"}
                    ),
                    "Action": actions,
                }
            ],
        },
        ensure_ascii=False,
    )
    blocks.extend(
        [
            "",
            f'resource "aws_ecr_repository_policy" "{ref}_policy" {{',
            f"  repository = aws_ecr_repository.{ref}.name",
            f"  policy     = jsonencode({document})",
            "}",
        ]
    )
    return "\n".join(blocks) + "\n"


def sqs_queue_block(node: GraphNode) -> str:
    """An ``aws_sqs_queue`` and optional queue policy."""
    ref = resource_name(node)
    principal = str(node.attributes.get("principal", _STAR))
    actions = node.attributes.get("actions") or ["sqs:SendMessage", "sqs:ReceiveMessage"]
    if not isinstance(actions, list):
        actions = [str(actions)]
    actions = [neutralize_hcl_openers(str(a)) for a in actions]

    blocks = [
        f'resource "aws_sqs_queue" "{ref}" {{',
        f"  name = {hcl_str(node.name)}",
        "  tags = local.common_tags",
        "}",
    ]
    document = json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "QueuePolicy",
                    "Effect": "Allow",
                    "Principal": (
                        _STAR if principal == _STAR else {"AWS": f"arn:aws:iam::{principal}:root"}
                    ),
                    "Action": actions,
                    "Resource": _STAR,
                }
            ],
        },
        ensure_ascii=False,
    )
    blocks.extend(
        [
            "",
            f'resource "aws_sqs_queue_policy" "{ref}_policy" {{',
            f"  queue_url = aws_sqs_queue.{ref}.id",
            f"  policy    = jsonencode({document})",
            "}",
        ]
    )
    return "\n".join(blocks) + "\n"


def build_services_tf(nodes: list[GraphNode]) -> str:
    ecr_nodes = [n for n in nodes if n.type == NodeType.ECR_REPOSITORY]
    sqs_nodes = [n for n in nodes if n.type == NodeType.SQS_QUEUE]
    if not ecr_nodes and not sqs_nodes:
        return _EMPTY
    blocks = [ecr_repository_block(n) for n in ecr_nodes] + [sqs_queue_block(n) for n in sqs_nodes]
    return "\n".join(blocks)
