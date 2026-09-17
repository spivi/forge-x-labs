"""EC2 instance and compute HCL blocks."""

from __future__ import annotations

from app.cloudforge import constants
from app.cloudforge.models.graph import GraphNode, NodeType
from app.cloudforge.pipeline.identifiers import resource_name

_EMPTY = constants.EMPTY_TF_HEADER


def ec2_instance_block(node: GraphNode) -> str:
    """An ``aws_instance``; optionally configured with IMDSv1."""
    ref = resource_name(node)
    imds_version = node.attributes.get("imds_version", "v2")
    tokens = "optional" if imds_version == "v1" else "required"
    lines = [
        f'resource "aws_instance" "{ref}" {{',
        '  ami           = "ami-00000000000000000"',
        '  instance_type = "t3.micro"',
        "  metadata_options {",
        '    http_endpoint = "enabled"',
        f'    http_tokens   = "{tokens}"',
        "  }",
        "  tags = local.common_tags",
        "}",
    ]
    return "\n".join(lines) + "\n"


def build_compute_tf(nodes: list[GraphNode]) -> str:
    instances = [n for n in nodes if n.type == NodeType.EC2_INSTANCE]
    if not instances:
        return _EMPTY
    blocks = [ec2_instance_block(n) for n in instances]
    return "\n".join(blocks)
