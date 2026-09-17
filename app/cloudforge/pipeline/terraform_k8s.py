"""Kubernetes Terraform blocks compiled from the risk graph. Never applied."""

from __future__ import annotations

from app.cloudforge import constants
from app.cloudforge.models.graph import GraphNode, NodeType
from app.cloudforge.pipeline.identifiers import resource_name
from app.cloudforge.pipeline.terraform_resource_blocks import hcl_str

_EMPTY = constants.EMPTY_TF_HEADER


def _attr(node: GraphNode, key: str, default: str) -> str:
    val = node.attributes.get(key, default)
    return val if isinstance(val, str) else default


def namespace_block(node: GraphNode) -> str:
    ref = resource_name(node)
    name = hcl_str(_attr(node, "namespace", node.name))
    return "\n".join(
        [
            f'resource "kubernetes_namespace" "{ref}" {{',
            "  metadata {",
            f"    name = {name}",
            "  }",
            "}",
            "",
        ]
    )


def service_account_block(node: GraphNode) -> str:
    ref = resource_name(node)
    ns = hcl_str(_attr(node, "namespace", "workloads"))
    role_arn = _attr(node, "role_arn", "")
    lines = [
        f'resource "kubernetes_service_account" "{ref}" {{',
        "  metadata {",
        f"    name      = {hcl_str(node.name)}",
        f"    namespace = {ns}",
    ]
    if role_arn:
        lines += [
            "    annotations = {",
            f'      "eks.amazonaws.com/role-arn" = {hcl_str(role_arn)}',
            "    }",
        ]
    lines += ["  }", "}", ""]
    return "\n".join(lines)


def pod_block(node: GraphNode) -> str:
    ref = resource_name(node)
    ns = hcl_str(_attr(node, "namespace", "workloads"))
    sa = hcl_str(_attr(node, "service_account", "default"))
    return "\n".join(
        [
            f'resource "kubernetes_pod" "{ref}" {{',
            "  metadata {",
            f"    name      = {hcl_str(node.name)}",
            f"    namespace = {ns}",
            "  }",
            "  spec {",
            f"    service_account_name = {sa}",
            "    container {",
            '      name  = "app"',
            '      image = "public.ecr.aws/nginx/nginx:1.25"',
            "    }",
            "  }",
            "}",
            "",
        ]
    )


_BUILDERS = {
    NodeType.K8S_NAMESPACE: namespace_block,
    NodeType.K8S_SERVICE_ACCOUNT: service_account_block,
    NodeType.K8S_POD: pod_block,
}


def build_k8s_tf(nodes: list[GraphNode]) -> str:
    blocks = [_BUILDERS[n.type](n) for n in nodes if n.type in _BUILDERS]
    return "".join(blocks) if blocks else _EMPTY
