"""Graph-aware Terraform provider blocks. Never applied."""

from __future__ import annotations

from app.cloudforge.models.graph import GraphNode, NodeType

_AWS = """terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
"""

_AWS_PROVIDER = """
provider "aws" {
  region                      = var.region
  access_key                  = "mock_access_key"
  secret_key                  = "mock_secret_key"
  skip_credentials_validation = true
  skip_requesting_account_id  = true
  skip_metadata_api_check     = true
}
"""

_AZURE_TYPES = {
    NodeType.AZURE_RESOURCE_GROUP,
    NodeType.AZURE_APP_SERVICE,
    NodeType.AZURE_MANAGED_IDENTITY,
    NodeType.AZURE_KEY_VAULT,
    NodeType.AZURE_STORAGE_CONTAINER,
}
_GCP_TYPES = {
    NodeType.GCP_PROJECT,
    NodeType.GCP_SERVICE_ACCOUNT,
    NodeType.GCP_WORKLOAD_IDENTITY_POOL,
    NodeType.GCP_STORAGE_BUCKET,
    NodeType.GCP_COMPUTE_INSTANCE,
}
_K8S_TYPES = {
    NodeType.K8S_NAMESPACE,
    NodeType.K8S_POD,
    NodeType.K8S_SERVICE_ACCOUNT,
    NodeType.K8S_SECRET,
    NodeType.K8S_ROLE,
    NodeType.K8S_ROLE_BINDING,
}


def build_providers_tf(nodes: list[GraphNode] | None = None) -> str:
    """AWS always. Azure, GCP, and Kubernetes only when those nodes exist."""
    types = {n.type for n in (nodes or [])}
    extra: list[str] = []
    if types & _AZURE_TYPES:
        extra.append(_AZURE_REQ)
    if types & _GCP_TYPES:
        extra.append(_GCP_REQ)
    if types & _K8S_TYPES:
        extra.append(_K8S_REQ)
    body = _AWS + "".join(extra) + "  }\n}\n" + _AWS_PROVIDER
    if types & _AZURE_TYPES:
        body += _AZURE_PROVIDER
    if types & _GCP_TYPES:
        body += _gcp_provider(nodes or [])
    if types & _K8S_TYPES:
        body += _K8S_PROVIDER
    return body


_AZURE_REQ = """    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
"""

_GCP_REQ = """    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
"""

_K8S_REQ = """    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.0"
    }
"""

_AZURE_PROVIDER = """
provider "azurerm" {
  features {}
  skip_provider_registration = true
  subscription_id            = "00000000-0000-0000-0000-000000000000"
  tenant_id                  = "00000000-0000-0000-0000-000000000000"
  client_id                  = "00000000-0000-0000-0000-000000000000"
  client_secret              = "mock"
}
"""

_K8S_PROVIDER = """
provider "kubernetes" {
  host     = "https://127.0.0.1:6443"
  insecure = true
}
"""


def _gcp_provider(nodes: list[GraphNode]) -> str:
    project = "mock-cloudforge"
    for node in nodes:
        if node.type == NodeType.GCP_PROJECT:
            raw = node.attributes.get("project_id", node.name)
            project = raw if isinstance(raw, str) else node.name
            break
    return f"""
provider "google" {{
  project = "{project}"
  region  = "us-central1"
}}
"""
