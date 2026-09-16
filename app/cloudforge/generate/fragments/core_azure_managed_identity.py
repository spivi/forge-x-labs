"""core.azure_imds_keyvault_harvest — Azure App Service IMDS Key Vault harvest."""

from __future__ import annotations

from random import Random
from typing import Any

from app.cloudforge.generate.fragments.base import FragmentBundle, register
from app.cloudforge.models.findings import ExpectedFinding, FindingFamily, GroundTruthPath
from app.cloudforge.models.graph import (
    EdgeSecurity,
    EdgeType,
    GraphEdge,
    GraphNode,
    NodeSecurity,
    NodeTags,
    NodeType,
)

_TAGS = NodeTags(env="prod", owner="azure-platform", app="customer-portal")


def _nid(ns: str, node_id: str) -> str:
    return f"{ns}/{node_id}" if ns else node_id


def _node(
    ns: str, node_id: str, ntype: NodeType, name: str, crit: str, **attrs: str | list[str]
) -> GraphNode:
    return GraphNode(
        id=_nid(ns, node_id),
        type=ntype,
        name=name,
        tags=_TAGS,
        security=NodeSecurity(criticality=crit),
        attributes=dict(attrs),
    )


def _edge(ns: str, src: str, dst: str, etype: EdgeType, risk: str) -> GraphEdge:
    return GraphEdge(
        from_=_nid(ns, src), to=_nid(ns, dst), type=etype, security=EdgeSecurity(risk=risk)
    )


def _ek(ns: str, src: str, etype: EdgeType, dst: str) -> str:
    return f"{_nid(ns, src)}->{etype.value}->{_nid(ns, dst)}"


@register("core.azure_imds_keyvault_harvest")
@register("core.azure_managed_identity")
class AzureManagedIdentity:
    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        return FragmentBundle(
            nodes=_nodes(ns), edges=_edges(ns), findings=_findings(ns), paths=[_critical(ns)]
        )


def _nodes(ns: str) -> list[GraphNode]:
    return [
        _node(
            ns,
            "sub-corp-prod",
            NodeType.AZURE_SUBSCRIPTION,
            "sub-corp-prod",
            "medium",
            subscription_id="00000000-0000-0000-0000-000000000001",
        ),
        _node(
            ns,
            "rg-workloads",
            NodeType.AZURE_RESOURCE_GROUP,
            "rg-workloads",
            "medium",
            location="eastus",
        ),
        _node(
            ns,
            "app-service-frontend",
            NodeType.AZURE_APP_SERVICE,
            "app-service-frontend",
            "high",
            identity_type="SystemAssigned",
            https_only="true",
        ),
        _node(
            ns,
            "id-app-service-frontend",
            NodeType.AZURE_MANAGED_IDENTITY,
            "id-app-service-frontend",
            "high",
            principal_id="11111111-1111-1111-1111-111111111111",
            identity_type="SystemAssigned",
        ),
        _node(
            ns,
            "kv-corp-secrets",
            NodeType.AZURE_KEY_VAULT,
            "kv-corp-secrets",
            "critical",
            sku="standard",
            purge_protection="false",
            secret_names=["storage-account-key"],
        ),
        _node(
            ns,
            "cnt-customer-financials",
            NodeType.AZURE_STORAGE_CONTAINER,
            "cnt-customer-financials",
            "critical",
            storage_account="stcorpfinancials",
            access_type="private",
        ),
        _node(
            ns,
            "customer-financials",
            NodeType.DATASET,
            "customer-financials",
            "critical",
            classification="restricted",
        ),
    ]


def _edges(ns: str) -> list[GraphEdge]:
    return [
        _edge(ns, "sub-corp-prod", "rg-workloads", EdgeType.ORGANIZATIONAL_CHILD, "none"),
        _edge(ns, "rg-workloads", "app-service-frontend", EdgeType.ORGANIZATIONAL_CHILD, "none"),
        _edge(ns, "app-service-frontend", "id-app-service-frontend", EdgeType.ASSUMES, "high"),
        _edge(ns, "id-app-service-frontend", "kv-corp-secrets", EdgeType.CAN_READ, "critical"),
        _edge(ns, "kv-corp-secrets", "cnt-customer-financials", EdgeType.CAN_READ, "critical"),
        _edge(
            ns,
            "cnt-customer-financials",
            "customer-financials",
            EdgeType.STORES_SENSITIVE_DATA,
            "critical",
        ),
    ]


def _findings(ns: str) -> list[ExpectedFinding]:
    return [
        ExpectedFinding(
            id=_nid(ns, "finding-azure-imds-keyvault-01"),
            severity="critical",
            family=FindingFamily.AZURE_IMDS_KEYVAULT_HARVEST,
            resource_ids=[
                _nid(ns, "app-service-frontend"),
                _nid(ns, "id-app-service-frontend"),
                _nid(ns, "kv-corp-secrets"),
            ],
            expected_scanner_visibility="visible",
            ground_truth=(
                "App Service managed identity enables IMDS secret harvesting from Key Vault"
            ),
            remediation=(
                "Enforce Azure Key Vault RBAC least privilege and enable Private Endpoints"
            ),
        ),
    ]


def _critical(ns: str) -> GroundTruthPath:
    return GroundTruthPath(
        id=_nid(ns, "path-critical-azure-imds-01"),
        severity="critical",
        nodes=[
            _nid(ns, "app-service-frontend"),
            _nid(ns, "id-app-service-frontend"),
            _nid(ns, "kv-corp-secrets"),
            _nid(ns, "cnt-customer-financials"),
            _nid(ns, "customer-financials"),
        ],
        edges=[
            _ek(ns, "app-service-frontend", EdgeType.ASSUMES, "id-app-service-frontend"),
            _ek(ns, "id-app-service-frontend", EdgeType.CAN_READ, "kv-corp-secrets"),
            _ek(ns, "kv-corp-secrets", EdgeType.CAN_READ, "cnt-customer-financials"),
            _ek(
                ns,
                "cnt-customer-financials",
                EdgeType.STORES_SENSITIVE_DATA,
                "customer-financials",
            ),
        ],
        explanation=(
            "SSRF against App Service queries IMDS for managed identity token, reads Key Vault "
            "secrets and accesses customer financial container"
        ),
    )
