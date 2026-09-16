"""KMS key and EBS snapshot HCL blocks (FXL-150). Own module: resource_blocks is full."""

from __future__ import annotations

import json

from app.cloudforge import constants
from app.cloudforge.models.graph import GraphNode
from app.cloudforge.pipeline.identifiers import resource_name
from app.cloudforge.pipeline.terraform_resource_blocks import hcl_str, neutralize_hcl_openers

_PUBLIC = "true"
_STAR = "*"


def kms_key_block(node: GraphNode) -> str:
    """An ``aws_kms_key`` whose policy principal/actions come from the graph."""
    ref = resource_name(node)
    principal = _str_attr(node, "principal", _STAR)
    actions = _actions(node) or ["kms:Decrypt"]
    document = json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": neutralize_hcl_openers(principal)},
                    "Action": actions,
                    "Resource": _STAR,
                }
            ],
        },
        ensure_ascii=False,
    )
    return (
        f'resource "aws_kms_key" "{ref}" {{\n'
        f"  description = {hcl_str(node.name)}\n"
        f"  policy      = jsonencode({document})\n"
        f"  tags        = local.common_tags\n"
        f"}}\n"
    )


def snapshot_block(node: GraphNode) -> str:
    """An unencrypted EBS snapshot; public ones get create-volume permission ``all``."""
    ref = resource_name(node)
    volume = _str_attr(node, "volume_id", constants.DUMMY_VOLUME_ID)
    block = (
        f'resource "aws_ebs_snapshot" "{ref}" {{\n'
        f"  volume_id = {hcl_str(volume)}\n"
        f"  encrypted = false\n"
        f"  tags      = local.common_tags\n"
        f"}}\n"
    )
    if node.attributes.get("public") == _PUBLIC:
        block += _public_permission(ref)
    return block


def _public_permission(ref: str) -> str:
    return (
        f'\nresource "aws_snapshot_create_volume_permission" "{ref}_public" {{\n'
        f"  snapshot_id = aws_ebs_snapshot.{ref}.id\n"
        f'  group       = "all"\n'
        f"}}\n"
    )


def _actions(node: GraphNode) -> list[str]:
    raw = node.attributes.get("actions", [])
    values = list(raw) if isinstance(raw, list) else [raw]
    return [neutralize_hcl_openers(str(action)) for action in values if action]


def _str_attr(node: GraphNode, key: str, default: str) -> str:
    raw = node.attributes.get(key, default)
    return raw if isinstance(raw, str) else default
