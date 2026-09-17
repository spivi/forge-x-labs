"""GCP Terraform blocks compiled from the risk graph. Never applied."""

from __future__ import annotations

from app.cloudforge import constants
from app.cloudforge.models.graph import GraphNode, NodeType
from app.cloudforge.pipeline.identifiers import resource_name
from app.cloudforge.pipeline.terraform_resource_blocks import hcl_str

_EMPTY = constants.EMPTY_TF_HEADER


def _attr(node: GraphNode, key: str, default: str) -> str:
    val = node.attributes.get(key, default)
    return val if isinstance(val, str) else default


def service_account_block(node: GraphNode) -> str:
    ref = resource_name(node)
    account_id = node.name.replace("_", "-")[:30]
    return "\n".join(
        [
            f'resource "google_service_account" "{ref}" {{',
            f"  account_id   = {hcl_str(account_id)}",
            f"  display_name = {hcl_str(node.name)}",
            "}",
            "",
        ]
    )


def workload_identity_pool_block(node: GraphNode) -> str:
    ref = resource_name(node)
    pool_id = node.name.replace("_", "-")[:32]
    return "\n".join(
        [
            f'resource "google_iam_workload_identity_pool" "{ref}" {{',
            f"  workload_identity_pool_id = {hcl_str(pool_id)}",
            f"  display_name              = {hcl_str(node.name)}",
            "}",
            "",
        ]
    )


def storage_bucket_block(node: GraphNode) -> str:
    ref = resource_name(node)
    name = hcl_str(_attr(node, "bucket_name", node.name))
    lines = [
        f'resource "google_storage_bucket" "{ref}" {{',
        f"  name     = {name}",
        '  location = "US"',
    ]
    # Access settings the graph declares: uniform bucket-level access is the
    # false-positive marker (no legacy ACL can open the bucket), public access
    # prevention ``enforced`` is the compensating control (no binding can either).
    if _attr(node, "uniform_bucket_level_access", "false") == "true":
        lines.append("  uniform_bucket_level_access = true")
    prevention = _attr(node, "public_access_prevention", "")
    if prevention in ("enforced", "inherited"):
        lines.append(f"  public_access_prevention = {hcl_str(prevention)}")
    return "\n".join([*lines, "}", ""])


_BUILDERS = {
    NodeType.GCP_SERVICE_ACCOUNT: service_account_block,
    NodeType.GCP_WORKLOAD_IDENTITY_POOL: workload_identity_pool_block,
    NodeType.GCP_STORAGE_BUCKET: storage_bucket_block,
}


def build_gcp_tf(nodes: list[GraphNode]) -> str:
    blocks = [_BUILDERS[n.type](n) for n in nodes if n.type in _BUILDERS]
    return "".join(blocks) if blocks else _EMPTY
