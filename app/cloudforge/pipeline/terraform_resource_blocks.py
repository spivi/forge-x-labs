"""Per-resource HCL block builders — one small pure function per resource kind.

Each builder takes a single ``GraphNode`` and returns a valid Terraform block
rendered from that node's ``type`` + ``attributes``. The emitter's per-file
assemblers (:mod:`terraform_blocks`) map a node list through these. All values are
safe fakes; the dummy account id is clearly marked. Only what the graph declares is
rendered — no destructive permissions are ever synthesized here.
"""

from __future__ import annotations

import json

from app.cloudforge import constants
from app.cloudforge.models.graph import GraphNode
from app.cloudforge.pipeline.identifiers import resource_name

__all__ = ["resource_name"]  # re-exported so existing call sites stay unchanged

_ACCOUNT = constants.DUMMY_ACCOUNT_ID
_INGRESS_PORT = constants.DEFAULT_INGRESS_PORT
_COMPENSATING_CONTROL = "compensating_control"


def neutralize_hcl_openers(value: str) -> str:
    """Rewrite HCL's live ``${`` / ``%{`` openers to their literal-escape form.

    HCL evaluates ``${...}`` / ``%{...}`` inside ANY double-quoted string — including the
    JSON string ``jsonencode(...)`` receives — so each opener is rewritten to HCL's own
    escape (``$${`` / ``%%{``). ``$``/``%`` are JSON-safe, so a later ``json.dumps`` keeps
    them. Shared core of :func:`hcl_str` AND the guard for untrusted scalars entering
    ``jsonencode``-wrapped policy documents, whose bytes are inert as JSON but LIVE HCL
    once wrapped (FXL-N2).
    """
    return value.replace("${", "$${").replace("%{", "%%{")


def hcl_str(value: str) -> str:
    """The single source of truth for a safely-quoted HCL string literal.

    Layers: (1) :func:`neutralize_hcl_openers` defuses live ``${``/``%{``; (2)
    ``json.dumps`` quotes and escapes ``"`` / ``\\`` / control chars so a hostile value
    cannot break out. Values entering ``jsonencode``-wrapped policy documents do NOT
    pass here and are neutralized at their own sinks (FXL-N2).

    ``ensure_ascii=False`` (FXL-N2): the default escapes astral-plane chars (e.g. an
    emoji) as a UTF-16 surrogate pair (``\\ud83d\\ude00``) that HCL cannot decode,
    breaking ``terraform validate``. Raw UTF-8 (the ``.tf`` files are UTF-8) is valid HCL.
    """
    return json.dumps(neutralize_hcl_openers(value), ensure_ascii=False)


def _actions(node: GraphNode) -> list[str]:
    """The node's declared IAM actions, neutralized for the ``jsonencode`` policy sink."""
    raw = node.attributes.get("actions", [])
    values = list(raw) if isinstance(raw, list) else [raw]
    return [neutralize_hcl_openers(action) for action in values]


def _resource_arn(node: GraphNode) -> str:
    """The node's declared resource arn, neutralized for the ``jsonencode`` policy sink."""
    raw = node.attributes.get("resource", "*")
    return neutralize_hcl_openers(raw) if isinstance(raw, str) else "*"


def _str_attr(node: GraphNode, key: str, default: str) -> str:
    """A single scalar attribute value as ``str`` (list-valued attrs fall back)."""
    raw = node.attributes.get(key, default)
    return raw if isinstance(raw, str) else default


def policy_condition(node: GraphNode) -> dict[str, dict[str, str]] | None:
    """The ``Condition`` block a resource policy carries when the node declares
    ``condition_key`` / ``condition_value`` (a compensating-control lookalike whose
    wildcard or external principal is scoped to the organization), else ``None``."""
    key = _str_attr(node, "condition_key", "")
    value = _str_attr(node, "condition_value", "")
    if not key or not value:
        return None
    return {"StringEquals": {neutralize_hcl_openers(key): neutralize_hcl_openers(value)}}


def with_condition(statement: dict[str, object], node: GraphNode) -> dict[str, object]:
    """``statement`` plus the node's policy condition, when it declares one."""
    condition = policy_condition(node)
    return {**statement, "Condition": condition} if condition else statement


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
    # ``ensure_ascii=False``: astral chars stay raw UTF-8, not HCL-undecodable surrogate
    # ``\\uXXXX`` pairs, inside this ``jsonencode`` string; scalars pre-neutralized (FXL-N2).
    document = json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {"Effect": "Allow", "Action": _actions(node), "Resource": _resource_arn(node)}
            ],
        },
        ensure_ascii=False,
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
    # ``_bucket_name`` carries untrusted ``node.name`` into this LIVE ``jsonencode`` HCL
    # string: neutralize openers + emit raw UTF-8 (not surrogate escapes) — FXL-N2.
    arn = neutralize_hcl_openers(f"arn:aws:s3:::{_bucket_name(node)}/public/*")
    document = json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {"Effect": "Allow", "Principal": "*", "Action": "s3:GetObject", "Resource": arn}
            ],
        },
        ensure_ascii=False,
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
