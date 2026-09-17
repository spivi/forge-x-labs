"""Azure, GCP, and Kubernetes nodes emit never-applied Terraform."""

from __future__ import annotations

from pathlib import Path

from app.cloudforge.generate.composer import GraphComposer
from app.cloudforge.io.loaders import load_yaml
from app.cloudforge.models.graph import GraphNode, NodeSecurity, NodeTags, NodeType
from app.cloudforge.models.scenario import ScenarioSpec
from app.cloudforge.pipeline import terraform_azure as azure
from app.cloudforge.pipeline import terraform_gcp as gcp
from app.cloudforge.pipeline.terraform_emitter import TerraformEmitter


def _emit(family: str, tmp_path: Path) -> dict[str, str]:
    data = load_yaml(Path(f"examples/{family}.yaml"))
    spec = ScenarioSpec.model_validate(data)
    graph = GraphComposer(spec, seed=0).generate().graph
    written = TerraformEmitter(graph).emit(tmp_path)
    return {p.name: p.read_text(encoding="utf-8") for p in written}


def test_k8s_family_emits_namespace_sa_pod_and_aws_iam(tmp_path: Path) -> None:
    files = _emit("k8s_pod_irsa_exfil", tmp_path)
    assert 'provider "kubernetes"' in files["providers.tf"]
    assert "kubernetes_namespace" in files["k8s.tf"]
    assert "kubernetes_service_account" in files["k8s.tf"]
    assert "kubernetes_pod" in files["k8s.tf"]
    assert "eks.amazonaws.com/role-arn" in files["k8s.tf"]
    assert "aws_iam_role" in files["iam.tf"]
    assert "aws_s3_bucket" in files["s3.tf"]


def test_azure_family_emits_rg_identity_vault_and_app(tmp_path: Path) -> None:
    files = _emit("azure_imds_keyvault_harvest", tmp_path)
    assert 'provider "azurerm"' in files["providers.tf"]
    assert "skip_provider_registration = true" in files["providers.tf"]
    assert "azurerm_resource_group" in files["azure.tf"]
    assert "azurerm_user_assigned_identity" in files["azure.tf"]
    assert "azurerm_key_vault" in files["azure.tf"]
    assert "azurerm_linux_web_app" in files["azure.tf"]
    assert "azurerm_storage_container" in files["azure.tf"]


def test_gcp_family_emits_wip_sa_and_bucket(tmp_path: Path) -> None:
    files = _emit("gcp_workload_identity_federation", tmp_path)
    assert 'provider "google"' in files["providers.tf"]
    assert "google_iam_workload_identity_pool" in files["gcp.tf"]
    assert "google_service_account" in files["gcp.tf"]
    assert "google_storage_bucket" in files["gcp.tf"]


def test_aws_family_does_not_pull_azure_provider(tmp_path: Path) -> None:
    files = _emit("ci_cd_iam_chain", tmp_path)
    assert 'provider "azurerm"' not in files["providers.tf"]
    assert 'provider "google"' not in files["providers.tf"]
    assert 'provider "kubernetes"' not in files["providers.tf"]
    assert files["azure.tf"].startswith("# No resources")
    assert files["gcp.tf"].startswith("# No resources")
    assert files["k8s.tf"].startswith("# No resources")


# --- attribute-driven control lines (1.4.0 vendor pools) -----------------------


def _node(ntype: NodeType, name: str, **attrs: str) -> GraphNode:
    return GraphNode(
        id=f"t0/{name}",
        type=ntype,
        name=name,
        tags=NodeTags(env="test", owner="t", app="t"),
        security=NodeSecurity(criticality="low"),
        attributes=dict(attrs),
    )


def test_key_vault_without_network_attributes_renders_as_before() -> None:
    text = azure.key_vault_block(_node(NodeType.AZURE_KEY_VAULT, "kv-plain"))
    assert "network_acls" not in text
    assert "public_network_access_enabled" not in text


def test_key_vault_with_network_rule_renders_deny_and_private_access() -> None:
    text = azure.key_vault_block(
        _node(
            NodeType.AZURE_KEY_VAULT,
            "kv-locked",
            public_network_access="Disabled",
            network_default_action="Deny",
        )
    )
    assert "public_network_access_enabled = false" in text
    assert 'default_action = "Deny"' in text
    assert 'bypass         = "AzureServices"' in text


def test_storage_container_disallowing_public_blobs_renders_the_account_flag() -> None:
    plain = azure.storage_container_block(_node(NodeType.AZURE_STORAGE_CONTAINER, "cnt-a"))
    locked = azure.storage_container_block(
        _node(NodeType.AZURE_STORAGE_CONTAINER, "cnt-b", allow_blob_public_access="false")
    )
    assert "allow_nested_items_to_be_public" not in plain
    assert "allow_nested_items_to_be_public = false" in locked
    assert 'container_access_type = "private"' in locked


def test_gcp_bucket_renders_uniform_access_and_public_access_prevention() -> None:
    plain = gcp.storage_bucket_block(_node(NodeType.GCP_STORAGE_BUCKET, "bkt-a"))
    guarded = gcp.storage_bucket_block(
        _node(
            NodeType.GCP_STORAGE_BUCKET,
            "bkt-b",
            uniform_bucket_level_access="true",
            public_access_prevention="enforced",
        )
    )
    assert "uniform_bucket_level_access" not in plain
    assert "public_access_prevention" not in plain
    assert "uniform_bucket_level_access = true" in guarded
    assert 'public_access_prevention = "enforced"' in guarded


def test_gcp_bucket_ignores_an_unknown_prevention_value() -> None:
    text = gcp.storage_bucket_block(
        _node(NodeType.GCP_STORAGE_BUCKET, "bkt-c", public_access_prevention="whatever")
    )
    assert "public_access_prevention" not in text


def test_vendor_padding_reaches_the_vendor_terraform(tmp_path: Path) -> None:
    """An Azure lab's filler is Azure: the vault network rule and the private
    container land in azure.tf, and the AWS files stay empty."""
    files = _emit("azure_imds_keyvault_harvest", tmp_path)
    assert files["iam.tf"].startswith("# No resources")
    assert files["s3.tf"].startswith("# No resources")
    assert files["services.tf"].startswith("# No resources")
    assert files["azure.tf"].count('resource "azurerm_') > 6
    files = _emit("gcp_workload_identity_federation", tmp_path / "gcp")
    assert files["iam.tf"].startswith("# No resources")
    assert files["s3.tf"].startswith("# No resources")
    assert files["gcp.tf"].count('resource "google_') > 3
