"""Database and secrets HCL blocks (FXL-154)."""

from __future__ import annotations

import json

from app.cloudforge import constants
from app.cloudforge.models.graph import GraphNode, NodeType
from app.cloudforge.pipeline.identifiers import resource_name
from app.cloudforge.pipeline.terraform_resource_blocks import hcl_str, neutralize_hcl_openers

_EMPTY = constants.EMPTY_TF_HEADER
_STAR = "*"


def rds_instance_block(node: GraphNode) -> str:
    """An ``aws_db_instance``; optionally publicly accessible."""
    ref = resource_name(node)
    public = str(node.attributes.get("publicly_accessible", "false")).lower() == "true"
    pub_str = "true" if public else "false"
    lines = [
        f'resource "aws_db_instance" "{ref}" {{',
        f"  identifier          = {hcl_str(node.name)}",
        "  allocated_storage   = 20",
        '  engine              = "postgres"',
        '  engine_version      = "15.3"',
        '  instance_class      = "db.t3.micro"',
        '  username            = "dbadmin"',
        '  password            = "dummy_password_never_deployed"',
        f"  publicly_accessible = {pub_str}",
        "  skip_final_snapshot = true",
        "  tags                = local.common_tags",
        "}",
    ]
    return "\n".join(lines) + "\n"


def secretsmanager_secret_block(node: GraphNode) -> str:
    """An ``aws_secretsmanager_secret`` and optional resource policy."""
    ref = resource_name(node)
    principal = str(node.attributes.get("principal", _STAR))
    actions = node.attributes.get("actions") or ["secretsmanager:GetSecretValue"]
    if not isinstance(actions, list):
        actions = [str(actions)]
    actions = [neutralize_hcl_openers(str(a)) for a in actions]

    blocks = [
        f'resource "aws_secretsmanager_secret" "{ref}" {{',
        f"  name = {hcl_str(node.name)}",
        "  tags = local.common_tags",
        "}",
    ]
    document = json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
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
            f'resource "aws_secretsmanager_secret_policy" "{ref}_policy" {{',
            f"  secret_arn = aws_secretsmanager_secret.{ref}.arn",
            f"  policy     = jsonencode({document})",
            "}",
        ]
    )
    return "\n".join(blocks) + "\n"


def build_database_tf(nodes: list[GraphNode]) -> str:
    rds_nodes = [n for n in nodes if n.type == NodeType.RDS_INSTANCE]
    sec_nodes = [n for n in nodes if n.type == NodeType.SECRETS_MANAGER_SECRET]
    if not rds_nodes and not sec_nodes:
        return _EMPTY
    blocks = [rds_instance_block(n) for n in rds_nodes] + [
        secretsmanager_secret_block(n) for n in sec_nodes
    ]
    return "\n".join(blocks)
