"""HCL string builders — static provider files plus graph-driven assemblers.

Terraform is a *compiled artifact* of the graph. It must be valid enough for
``terraform validate`` and for static scanners (checkov/opa) to have real
resources to flag, but it is never applied. All values are safe fakes; the dummy
account id is clearly marked.

``providers.tf`` / ``variables.tf`` / ``main.tf`` are family-independent (provider
config + fake account id + common tags). ``iam.tf`` / ``s3.tf`` / ``network.tf`` are
assembled per-family from the scenario graph nodes via
:mod:`terraform_resource_blocks`. The intentional misconfigurations (broad S3 read,
missing logging, a 0.0.0.0/0 security group) come straight from the graph — they are
the modeled risks. No destructive permissions are ever synthesized.
"""

from __future__ import annotations

from collections.abc import Callable

from app.cloudforge import constants
from app.cloudforge.models.graph import GraphNode, NodeTags, NodeType
from app.cloudforge.pipeline import terraform_kms_snapshot as kms_snap
from app.cloudforge.pipeline import terraform_resource_blocks as res
from app.cloudforge.pipeline.terraform_resource_blocks import hcl_str

_DUMMY = constants.DUMMY_ACCOUNT_ID
_REGION = constants.DEFAULT_REGION
_EMPTY = constants.EMPTY_TF_HEADER
# Safe placeholder tags for a graph with no nodes (keeps ``derive_common_tags`` total).
_UNKNOWN_TAG = "unknown"


# --- static, family-independent files ----------------------------------------


def build_providers_tf() -> str:
    return """terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region                      = var.region
  access_key                  = "mock_access_key"
  secret_key                  = "mock_secret_key"
  skip_credentials_validation = true
  skip_requesting_account_id  = true
  skip_metadata_api_check     = true
}
"""


def build_variables_tf() -> str:
    return f"""variable "region" {{
  type    = string
  default = "{_REGION}"
}}

# DUMMY / non-routable fake account id — this scenario is never deployed.
variable "account_id" {{
  type    = string
  default = "{_DUMMY}"
}}
"""


def derive_common_tags(nodes: list[GraphNode]) -> NodeTags:
    """The family's representative tags: the Account/root node's, else the first node's.

    Each family stamps every node with one tag set, so the Account node is a stable,
    unambiguous source; falling back to the first node covers graphs without one. An
    empty node list has no source at all, so the function stays total by returning a
    safe ``"unknown"`` placeholder tag set instead of indexing ``nodes[0]``.
    """
    if not nodes:
        return NodeTags(env=_UNKNOWN_TAG, owner=_UNKNOWN_TAG, app=_UNKNOWN_TAG)
    accounts = _of_type(nodes, NodeType.ACCOUNT)
    source = accounts[0] if accounts else nodes[0]
    return source.tags


def build_main_tf(tags: NodeTags) -> str:
    """Emit ``locals.common_tags`` from the graph-derived tags (not hardcoded)."""
    return f"""locals {{
  fake_account_id = "{_DUMMY}"
  common_tags = {{
    env   = {hcl_str(tags.env)}
    owner = {hcl_str(tags.owner)}
    app   = {hcl_str(tags.app)}
  }}
}}
"""


# --- graph-driven files ------------------------------------------------------


def _render(nodes: list[GraphNode], builder: Callable[[GraphNode], str]) -> str:
    """Join per-node blocks, or the empty-file header when no node matches."""
    blocks = [builder(node) for node in nodes]
    return "\n".join(blocks) if blocks else _EMPTY


def _of_type(nodes: list[GraphNode], *types: NodeType) -> list[GraphNode]:
    wanted = set(types)
    return [node for node in nodes if node.type in wanted]


def build_iam_tf(nodes: list[GraphNode]) -> str:
    """Render one role per IAMRole node and one policy per IAMPolicy node."""
    roles = _of_type(nodes, NodeType.IAM_ROLE)
    policies = _of_type(nodes, NodeType.IAM_POLICY)
    blocks = [res.role_block(n) for n in roles] + [res.policy_block(n) for n in policies]
    return "\n".join(blocks) if blocks else _EMPTY


def build_s3_tf(nodes: list[GraphNode]) -> str:
    """Render one bucket per S3Bucket node (+ policy for compensating controls)."""
    return _render(_of_type(nodes, NodeType.S3_BUCKET), res.bucket_block)


def build_network_tf(nodes: list[GraphNode]) -> str:
    """Render VPC / Subnet / SecurityGroup nodes, wiring both to the VPC."""
    vpcs = _of_type(nodes, NodeType.VPC)
    vpc_ref = res.resource_name(vpcs[0]) if vpcs else None
    blocks: list[str] = [res.vpc_block(n) for n in vpcs]
    blocks += [res.subnet_block(n, vpc_ref) for n in _of_type(nodes, NodeType.SUBNET)]
    blocks += [
        res.security_group_block(n, vpc_ref) for n in _of_type(nodes, NodeType.SECURITY_GROUP)
    ]
    return "\n".join(blocks) if blocks else _EMPTY


def build_kms_tf(nodes: list[GraphNode]) -> str:
    """Render one KMS key per KmsKey node."""
    return _render(_of_type(nodes, NodeType.KMS_KEY), kms_snap.kms_key_block)


def build_snapshot_tf(nodes: list[GraphNode]) -> str:
    """Render one EBS snapshot per EbsSnapshot node."""
    return _render(_of_type(nodes, NodeType.EBS_SNAPSHOT), kms_snap.snapshot_block)
