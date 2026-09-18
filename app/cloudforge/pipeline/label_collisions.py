"""Pre-emission guard against duplicate Terraform resource labels.

:func:`resource_name` sanitizes any ``node.id`` to a Terraform-legal label
(``[^A-Za-z0-9_]`` -> ``_``, leading-char guard). Distinct node ids that differ
ONLY by an illegal char / ``-`` / ``_`` swap therefore sanitize to the SAME label
(e.g. ``a-b`` and ``a_b`` both -> ``a_b``). Terraform then errors on a duplicate
resource label (``Duplicate resource "aws_s3_bucket"``), turning an
externally-authored graph into a ``terraform validate`` DoS.

A generator that produces such a collision is buggy, so we fail loud rather than
silently uniquify: :func:`check_label_collisions` detects the clash BEFORE emission
and raises :class:`GraphIntegrityError` naming both node ids and the shared label.

Scope is per resource TYPE: Terraform labels only collide within the same resource
``"type"`` (two ``aws_s3_bucket`` with label ``x``), so the check is keyed by the
node's emitted resource type. Node types that emit no resource carry no label and
are skipped.
"""

from __future__ import annotations

from app.cloudforge.errors import GraphIntegrityError
from app.cloudforge.models.graph import GraphNode, NodeType
from app.cloudforge.pipeline.identifiers import resource_name

# The Terraform resource ``"type"`` each node type emits. Node types absent here
# (ACCOUNT / CICDIdentity / Application / DataSet / LogTrail) emit no resource, so
# they carry no label and cannot collide. Mirrors the block assemblers in
# :mod:`terraform_blocks`.
_RESOURCE_TYPE_BY_NODE_TYPE: dict[NodeType, str] = {
    NodeType.IAM_ROLE: "aws_iam_role",
    NodeType.IAM_POLICY: "aws_iam_policy",
    NodeType.S3_BUCKET: "aws_s3_bucket",
    NodeType.VPC: "aws_vpc",
    NodeType.SUBNET: "aws_subnet",
    NodeType.SECURITY_GROUP: "aws_security_group",
    NodeType.KMS_KEY: "aws_kms_key",
    NodeType.EBS_SNAPSHOT: "aws_ebs_snapshot",
    NodeType.EC2_INSTANCE: "aws_instance",
    NodeType.LAMBDA_FUNCTION: "aws_lambda_function",
    NodeType.SECRETS_MANAGER_SECRET: "aws_secretsmanager_secret",
    NodeType.RDS_INSTANCE: "aws_db_instance",
    NodeType.ECR_REPOSITORY: "aws_ecr_repository",
    NodeType.SQS_QUEUE: "aws_sqs_queue",
    NodeType.AZURE_RESOURCE_GROUP: "azurerm_resource_group",
    NodeType.AZURE_APP_SERVICE: "azurerm_linux_web_app",
    NodeType.AZURE_MANAGED_IDENTITY: "azurerm_user_assigned_identity",
    NodeType.AZURE_KEY_VAULT: "azurerm_key_vault",
    NodeType.AZURE_STORAGE_CONTAINER: "azurerm_storage_container",
    NodeType.GCP_SERVICE_ACCOUNT: "google_service_account",
    NodeType.GCP_WORKLOAD_IDENTITY_POOL: "google_iam_workload_identity_pool",
    NodeType.GCP_STORAGE_BUCKET: "google_storage_bucket",
    NodeType.K8S_NAMESPACE: "kubernetes_namespace",
    NodeType.K8S_SERVICE_ACCOUNT: "kubernetes_service_account",
    NodeType.K8S_POD: "kubernetes_pod",
}


def check_label_collisions(nodes: list[GraphNode]) -> None:
    """Raise :class:`GraphIntegrityError` if two distinct node ids share a label.

    The check is scoped per emitted resource type: only nodes whose labels live in
    the same Terraform ``resource "<type>"`` namespace can collide. The first clash
    found is reported with both node ids and the shared ``(type, label)``.
    """
    seen: dict[tuple[str, str], str] = {}
    for node in nodes:
        resource_type = _RESOURCE_TYPE_BY_NODE_TYPE.get(node.type)
        if resource_type is None:
            continue
        label = resource_name(node)
        key = (resource_type, label)
        prior_id = seen.get(key)
        if prior_id is not None and prior_id != node.id:
            raise GraphIntegrityError(
                f"duplicate Terraform resource label {label!r} for "
                f'resource "{resource_type}": node ids {prior_id!r} and {node.id!r} '
                f"both sanitize to it (distinct nodes must not collide)"
            )
        seen[key] = node.id
