"""Lambda function and serverless HCL blocks (FXL-154)."""

from __future__ import annotations

from app.cloudforge import constants
from app.cloudforge.models.graph import GraphNode, NodeType
from app.cloudforge.pipeline.identifiers import resource_name
from app.cloudforge.pipeline.terraform_resource_blocks import hcl_str

_EMPTY = constants.EMPTY_TF_HEADER


def lambda_function_block(node: GraphNode) -> str:
    """An ``aws_lambda_function`` and optional ``aws_lambda_function_url``."""
    ref = resource_name(node)
    auth_type = node.attributes.get("auth_type", "NONE")
    blocks = [
        f'resource "aws_lambda_function" "{ref}" {{',
        f"  function_name = {hcl_str(node.name)}",
        '  role          = "arn:aws:iam::000000000000:role/dummy_lambda_role"',
        '  runtime       = "python3.12"',
        '  handler       = "index.handler"',
        '  s3_bucket     = "dummy-code-bucket-000000000000"',
        '  s3_key        = "function.zip"',
        "  tags          = local.common_tags",
        "}",
    ]
    if auth_type:
        blocks.extend(
            [
                "",
                f'resource "aws_lambda_function_url" "{ref}_url" {{',
                f"  function_name      = aws_lambda_function.{ref}.function_name",
                f'  authorization_type = "{auth_type}"',
                "}",
            ]
        )
    return "\n".join(blocks) + "\n"


def build_serverless_tf(nodes: list[GraphNode]) -> str:
    lambdas = [n for n in nodes if n.type == NodeType.LAMBDA_FUNCTION]
    if not lambdas:
        return _EMPTY
    blocks = [lambda_function_block(n) for n in lambdas]
    return "\n".join(blocks)
