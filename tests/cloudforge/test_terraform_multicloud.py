"""Azure, GCP, and Kubernetes nodes emit never-applied Terraform."""

from __future__ import annotations

from pathlib import Path

from app.cloudforge.generate.composer import GraphComposer
from app.cloudforge.io.loaders import load_yaml
from app.cloudforge.models.scenario import ScenarioSpec
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
