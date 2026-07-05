"""Per-resource HCL block builders — one small pure function per resource kind.

Each builder takes a single ``GraphNode`` and returns a valid Terraform block
rendered from that node's ``type`` + ``attributes``. The emitter's per-file
assemblers (:mod:`terraform_blocks`) map a node list through these. Splitting the
blocks out keeps every module under the 200-line limit and every function under
30 lines.

All values are safe fakes; the dummy account id is clearly marked. Only what the
graph declares is rendered — no destructive permissions are ever synthesized here.
"""

from __future__ import annotations

import json
import re

from app.cloudforge import constants
from app.cloudforge.models.graph import GraphNode

_ACCOUNT = constants.DUMMY_ACCOUNT_ID
_INGRESS_PORT = constants.DEFAULT_INGRESS_PORT
_COMPENSATING_CONTROL = "compensating_control"

# Any char outside the Terraform-legal identifier charset collapses to ``_``.
_ILLEGAL_ID_CHAR = re.compile(r"[^A-Za-z0-9_]")
# A Terraform label must start with a letter or underscore, never a digit.
_LEADING_DIGIT = re.compile(r"^[0-9]")


def hcl_str(value: str) -> str:
    """The single source of truth for a safely-quoted HCL string literal.

    Two escaping layers, both required:

    1. HCL evaluates ``${...}`` (interpolation) and ``%{...}`` (template directives)
       *inside* a double-quoted string. ``json.dumps`` leaves ``$``/``%``/``{``
       untouched, so those openers would stay live. We first neutralize them with
       HCL's own literal-escape sequences (``$${`` / ``%%{``) on the raw value —
       ``$``/``%`` are JSON-safe, so the later ``json.dumps`` preserves them verbatim.
    2. ``json.dumps`` then quotes and escapes ``"``, ``\\`` and control chars
       (newlines), so a hostile value can no longer break out of the string.

    Every scalar string entering emitted HCL must pass through here; JSON policy
    documents built via ``json.dumps`` are already inert (they are not HCL strings).
    """
    neutralized = value.replace("${", "$${").replace("%{", "%%{")
    return json.dumps(neutralized)


def resource_name(node: GraphNode) -> str:
    """A Terraform-legal local resource-label identifier for ANY ``node.id``.

    The label sits at the resource-LABEL position (``resource "type" "<label>"``),
    which is a bare identifier — not a quotable string — so ``hcl_str`` cannot guard
    it. We map every char outside ``[A-Za-z0-9_]`` to ``_`` (closing the label-breakout
    surface) and guarantee a valid leading char: a Terraform label must start with a
    letter or underscore, so an empty or digit-leading result is prefixed with ``_``.
    The output always matches ``^[A-Za-z_][A-Za-z0-9_]*$``.
    """
    sanitized = _ILLEGAL_ID_CHAR.sub("_", node.id)
    if not sanitized or _LEADING_DIGIT.match(sanitized):
        return f"_{sanitized}"
    return sanitized


def _actions(node: GraphNode) -> list[str]:
    raw = node.attributes.get("actions", [])
    return list(raw) if isinstance(raw, list) else [raw]


def _resource_arn(node: GraphNode) -> str:
    raw = node.attributes.get("resource", "*")
    return raw if isinstance(raw, str) else "*"


def _str_attr(node: GraphNode, key: str, default: str) -> str:
    """A single scalar attribute value as ``str`` (list-valued attrs fall back)."""
    raw = node.attributes.get(key, default)
    return raw if isinstance(raw, str) else default


def _bucket_name(node: GraphNode) -> str:
    return f"{node.name}-{node.tags.env}-{_ACCOUNT}"


def role_block(node: GraphNode) -> str:
    """An IAM role with a generic assume-role policy (the chain is the risk)."""
    ref = resource_name(node)
    trust = json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {"Effect": "Allow", "Principal": {"AWS": "*"}, "Action": "sts:AssumeRole"}
            ],
        }
    )
    return (
        f'resource "aws_iam_role" "{ref}" {{\n'
        f"  name               = {hcl_str(node.name)}\n"
        f"  assume_role_policy = jsonencode({trust})\n"
        f"  tags               = local.common_tags\n"
        f"}}\n"
    )


def policy_block(node: GraphNode) -> str:
    """A standalone IAM policy from the node's declared actions + resource arn."""
    ref = resource_name(node)
    document = json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": _actions(node),
                    "Resource": _resource_arn(node),
                }
            ],
        }
    )
    return (
        f'resource "aws_iam_policy" "{ref}" {{\n'
        f"  name   = {hcl_str(node.name)}\n"
        f"  policy = jsonencode({document})\n"
        f"}}\n"
    )


def bucket_block(node: GraphNode) -> str:
    """An S3 bucket; adds a public-read bucket policy for a compensating control."""
    ref = resource_name(node)
    block = (
        f'resource "aws_s3_bucket" "{ref}" {{\n'
        f"  bucket = {hcl_str(_bucket_name(node))}\n"
        f"  tags   = local.common_tags\n"
        f"}}\n"
    )
    if node.attributes.get(_COMPENSATING_CONTROL) == "true":
        block += _bucket_policy_block(node)
    return block


def _bucket_policy_block(node: GraphNode) -> str:
    ref = resource_name(node)
    document = json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": "s3:GetObject",
                    "Resource": f"arn:aws:s3:::{_bucket_name(node)}/public/*",
                }
            ],
        }
    )
    return (
        f'\nresource "aws_s3_bucket_policy" "{ref}" {{\n'
        f"  bucket = aws_s3_bucket.{ref}.id\n"
        f"  policy = jsonencode({document})\n"
        f"}}\n"
    )


def vpc_block(node: GraphNode) -> str:
    cidr = _str_attr(node, "cidr", "10.0.0.0/16")
    return (
        f'resource "aws_vpc" "{resource_name(node)}" {{\n'
        f"  cidr_block = {hcl_str(cidr)}\n"
        f"  tags       = local.common_tags\n"
        f"}}\n"
    )


def subnet_block(node: GraphNode, vpc_ref: str | None) -> str:
    cidr = _str_attr(node, "cidr", "10.0.1.0/24")
    vpc_line = f"  vpc_id     = aws_vpc.{vpc_ref}.id\n" if vpc_ref else ""
    return (
        f'resource "aws_subnet" "{resource_name(node)}" {{\n'
        f"{vpc_line}"
        f"  cidr_block = {hcl_str(cidr)}\n"
        f"  tags       = local.common_tags\n"
        f"}}\n"
    )


def security_group_block(node: GraphNode, vpc_ref: str | None) -> str:
    """A security group whose ingress CIDR is the modeled exposure risk."""
    ref = resource_name(node)
    ingress_cidr = _str_attr(node, "ingress_cidr", "0.0.0.0/0")
    vpc_line = f"  vpc_id = aws_vpc.{vpc_ref}.id\n" if vpc_ref else ""
    return (
        f'resource "aws_security_group" "{ref}" {{\n'
        f"  name   = {hcl_str(node.name)}\n"
        f"{vpc_line}\n"
        f"  ingress {{\n"
        f"    from_port   = {_INGRESS_PORT}\n"
        f"    to_port     = {_INGRESS_PORT}\n"
        f'    protocol    = "tcp"\n'
        f"    cidr_blocks = [{hcl_str(ingress_cidr)}]\n"
        f"  }}\n\n"
        f"  egress {{\n"
        f"    from_port   = 0\n"
        f"    to_port     = 0\n"
        f'    protocol    = "-1"\n'
        f'    cidr_blocks = ["0.0.0.0/0"]\n'
        f"  }}\n\n"
        f"  tags = local.common_tags\n"
        f"}}\n"
    )
