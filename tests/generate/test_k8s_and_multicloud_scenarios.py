"""Tests for K8s IRSA and Multi-Cloud (Azure, GCP) scenario fragments."""

from __future__ import annotations

from random import Random
from typing import Literal

from app.cloudforge.generate.composer import GraphComposer
from app.cloudforge.generate.fragments.base import get_fragment
from app.cloudforge.models.findings import FindingFamily
from app.cloudforge.models.graph import EdgeType, NodeType, ScenarioGraph
from app.cloudforge.models.scenario import (
    CompanyProfile,
    Constraints,
    Requirements,
    ScenarioSpec,
)


def _spec(
    scenario_type: str,
    cloud: Literal["aws", "azure", "gcp", "k8s", "multi_cloud"],
) -> ScenarioSpec:
    return ScenarioSpec(
        cloud=cloud,
        scenario_type=scenario_type,
        environment="production",
        difficulty="hard",
        company_profile=CompanyProfile(type="fintech", size="enterprise", app_name="banking"),
        requirements=Requirements(critical_chains=1, medium_findings=0, false_positives=0),
        constraints=Constraints(
            no_real_secrets=True,
            no_destructive_permissions=True,
            max_resources=20,
            deployable=False,
        ),
        scale_profile="small",
    )


def test_k8s_irsa_fragment() -> None:
    frag = get_fragment("core.k8s_pod_irsa_exfil")
    bundle = frag.build("test-k8s", Random(42), {})

    node_types = {n.type for n in bundle.nodes}
    assert NodeType.K8S_CLUSTER in node_types
    assert NodeType.K8S_NAMESPACE in node_types
    assert NodeType.K8S_SERVICE_ACCOUNT in node_types
    assert NodeType.K8S_POD in node_types
    assert NodeType.IAM_ROLE in node_types
    assert NodeType.S3_BUCKET in node_types
    assert NodeType.DATASET in node_types

    edge_types = [e.type for e in bundle.edges]
    assert EdgeType.IN_NAMESPACE in edge_types
    assert EdgeType.BINDS_SERVICE_ACCOUNT in edge_types
    assert EdgeType.FEDERATES_TO in edge_types
    assert EdgeType.CAN_READ in edge_types
    assert EdgeType.STORES_SENSITIVE_DATA in edge_types

    assert len(bundle.findings) >= 1
    assert bundle.findings[0].family == FindingFamily.K8S_POD_IRSA_EXFIL
    assert len(bundle.paths) >= 1

    graph = ScenarioGraph(nodes=bundle.nodes, edges=bundle.edges)
    assert len(graph.nodes) == 7


def test_azure_managed_identity_fragment() -> None:
    frag = get_fragment("core.azure_imds_keyvault_harvest")
    bundle = frag.build("test-azure", Random(42), {})

    node_types = {n.type for n in bundle.nodes}
    assert NodeType.AZURE_SUBSCRIPTION in node_types
    assert NodeType.AZURE_RESOURCE_GROUP in node_types
    assert NodeType.AZURE_APP_SERVICE in node_types
    assert NodeType.AZURE_MANAGED_IDENTITY in node_types
    assert NodeType.AZURE_KEY_VAULT in node_types
    assert NodeType.AZURE_STORAGE_CONTAINER in node_types

    assert len(bundle.findings) >= 1
    assert bundle.findings[0].family == FindingFamily.AZURE_IMDS_KEYVAULT_HARVEST
    graph = ScenarioGraph(nodes=bundle.nodes, edges=bundle.edges)
    assert len(graph.nodes) == 7


def test_gcp_workload_identity_fragment() -> None:
    frag = get_fragment("core.gcp_workload_identity_federation")
    bundle = frag.build("test-gcp", Random(42), {})

    node_types = {n.type for n in bundle.nodes}
    assert NodeType.GCP_ORGANIZATION in node_types
    assert NodeType.GCP_PROJECT in node_types
    assert NodeType.GCP_WORKLOAD_IDENTITY_POOL in node_types
    assert NodeType.GCP_SERVICE_ACCOUNT in node_types
    assert NodeType.GCP_STORAGE_BUCKET in node_types

    assert len(bundle.findings) >= 1
    assert bundle.findings[0].family == FindingFamily.GCP_WORKLOAD_IDENTITY_FEDERATION
    graph = ScenarioGraph(nodes=bundle.nodes, edges=bundle.edges)
    assert len(graph.nodes) == 6


def test_composer_generates_all_three() -> None:
    cases: list[tuple[str, Literal["aws", "azure", "gcp", "k8s", "multi_cloud"]]] = [
        ("k8s_pod_irsa_exfil", "k8s"),
        ("azure_imds_keyvault_harvest", "azure"),
        ("gcp_workload_identity_federation", "gcp"),
    ]
    for st, cl in cases:
        bundle = GraphComposer(_spec(st, cl), seed=10).generate()
        assert len(bundle.graph.nodes) >= 5
        assert len(bundle.findings.findings) >= 1
        assert len(bundle.ground_truth.paths) >= 1
