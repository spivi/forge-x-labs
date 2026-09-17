"""core.azure_imds_keyvault_harvest: an App Service token walks to customer data.

Story: SSRF against app-service-frontend queries IMDS for the token of its
system-assigned identity. On the direct chain that identity reads
kv-corp-secrets, whose stored storage key opens the customer financials
container. With ``extra_hops`` the identity first holds Managed Identity
Operator over a chain of user-assigned identities and obtains each one's token
in turn; the last one reads the vault. With ``dead_end`` the app service also
holds a second identity whose only grant reaches a container of build output.
"""

from __future__ import annotations

from random import Random
from typing import Any

from app.cloudforge.generate.fragments._core import Kit, Piece, draw_hops, hop_lines, shape_of
from app.cloudforge.generate.fragments._vocab import AZURE_DEAD_ENDS, AZURE_HOP_IDENTITIES
from app.cloudforge.generate.fragments.base import FragmentBundle, register, register_core
from app.cloudforge.models.findings import (
    ExpectedFinding,
    FindingFamily,
    GroundTruthPath,
    SinkKind,
)
from app.cloudforge.models.graph import EdgeType, GraphEdge, GraphNode, NodeTags, NodeType

_TAGS = NodeTags(env="prod", owner="azure-platform", app="customer-portal")
_RESOURCE_GROUP = "rg-workloads"
_ENTRY = "app-service-frontend"
_HEAD = "id-app-service-frontend"
_VAULT = "kv-corp-secrets"
_CONTAINER = "cnt-customer-financials"
_SINK = "customer-financials"
_HOP_VERB = "holds Managed Identity Operator over and obtains the token of"


@register_core
@register("core.azure_managed_identity")
class AzureManagedIdentity:
    scenario_type = "azure_imds_keyvault_harvest"
    cloud = "azure"
    prompt = (
        "An App Service has a managed identity. Can it reach secrets or customer "
        "data that a human operator would not expect it to hold?"
    )
    checklist = ("azure_imds_keyvault_harvest", "Azure: App Service Key Vault Harvest")
    teaching_point = "App Service IMDS -> Key Vault"

    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        kit = Kit(ns, _TAGS)
        shape = shape_of(params)
        hops = draw_hops(
            kit,
            rng,
            shape.extra_hops,
            AZURE_HOP_IDENTITIES,
            "id",
            NodeType.AZURE_MANAGED_IDENTITY,
            identity_type="UserAssigned",
            resource_group_name=_RESOURCE_GROUP,
        )
        chain = [_HEAD, *hops.ids]
        nodes = _nodes(kit) + hops.nodes
        edges = _edges(kit, chain)
        if shape.dead_end:
            branch = _dead_end(kit, rng)
            nodes, edges = nodes + branch.nodes, edges + branch.edges
        names = [_HEAD, *hops.names]
        return FragmentBundle(
            nodes=nodes,
            edges=edges,
            findings=_findings(kit, chain[-1]),
            paths=[_critical(kit, chain, names)],
        )


def _nodes(kit: Kit) -> list[GraphNode]:
    return [
        kit.node(
            "sub-corp-prod",
            NodeType.AZURE_SUBSCRIPTION,
            "sub-corp-prod",
            "medium",
            subscription_id="00000000-0000-0000-0000-000000000001",
        ),
        kit.node(
            _RESOURCE_GROUP,
            NodeType.AZURE_RESOURCE_GROUP,
            _RESOURCE_GROUP,
            "medium",
            location="eastus",
        ),
        kit.node(
            _ENTRY,
            NodeType.AZURE_APP_SERVICE,
            _ENTRY,
            "high",
            identity_type="SystemAssigned",
            https_only="true",
        ),
        kit.node(
            _HEAD,
            NodeType.AZURE_MANAGED_IDENTITY,
            _HEAD,
            "high",
            principal_id="11111111-1111-1111-1111-111111111111",
            identity_type="SystemAssigned",
        ),
        kit.node(
            _VAULT,
            NodeType.AZURE_KEY_VAULT,
            _VAULT,
            "critical",
            sku="standard",
            purge_protection="false",
            secret_names=["storage-account-key"],
        ),
        kit.node(
            _CONTAINER,
            NodeType.AZURE_STORAGE_CONTAINER,
            _CONTAINER,
            "critical",
            storage_account="stcorpfinancials",
            access_type="private",
        ),
        kit.node(_SINK, NodeType.DATASET, _SINK, "critical", classification="restricted"),
    ]


def _edges(kit: Kit, chain: list[str]) -> list[GraphEdge]:
    reader = chain[-1]
    return [
        kit.edge("sub-corp-prod", _RESOURCE_GROUP, EdgeType.ORGANIZATIONAL_CHILD, "none"),
        kit.edge(_RESOURCE_GROUP, _ENTRY, EdgeType.ORGANIZATIONAL_CHILD, "none"),
        kit.edge(_ENTRY, _HEAD, EdgeType.ASSUMES, "high"),
        *kit.chain(chain, EdgeType.ASSUMES, "critical"),
        kit.edge(reader, _VAULT, EdgeType.CAN_READ, "critical"),
        kit.edge(_VAULT, _CONTAINER, EdgeType.CAN_READ, "critical"),
        kit.edge(_CONTAINER, _SINK, EdgeType.STORES_SENSITIVE_DATA, "critical"),
    ]


def _dead_end(kit: Kit, rng: Random) -> Piece:
    """A second identity the app service holds, granted only a build container."""
    identity_name, container_name, account = rng.choice(AZURE_DEAD_ENDS)
    return Piece(
        nodes=[
            kit.node(
                identity_name,
                NodeType.AZURE_MANAGED_IDENTITY,
                identity_name,
                "low",
                identity_type="UserAssigned",
                role_definition="Storage Blob Data Contributor",
                resource_group_name=_RESOURCE_GROUP,
            ),
            kit.node(
                container_name,
                NodeType.AZURE_STORAGE_CONTAINER,
                container_name,
                "low",
                storage_account=account,
                access_type="private",
            ),
        ],
        edges=[
            kit.edge(_ENTRY, identity_name, EdgeType.ASSUMES, "low"),
            kit.edge(identity_name, container_name, EdgeType.CAN_READ, "low"),
        ],
    )


def _findings(kit: Kit, reader: str) -> list[ExpectedFinding]:
    resources = [kit.nid(_ENTRY), kit.nid(_HEAD), kit.nid(reader), kit.nid(_VAULT)]
    return [
        ExpectedFinding(
            id=kit.nid("finding-azure-imds-keyvault-01"),
            severity="critical",
            family=FindingFamily.AZURE_IMDS_KEYVAULT_HARVEST,
            resource_ids=list(dict.fromkeys(resources)),
            expected_scanner_visibility="visible",
            ground_truth=(
                "App Service managed identity enables IMDS secret harvesting from Key Vault"
            ),
            remediation=(
                "Enforce Azure Key Vault RBAC least privilege and enable Private Endpoints"
            ),
        ),
    ]


def _critical(kit: Kit, chain: list[str], names: list[str]) -> GroundTruthPath:
    reader = chain[-1]
    return GroundTruthPath(
        id=kit.nid("path-critical-azure-imds-01"),
        severity="critical",
        nodes=[kit.nid(n) for n in [_ENTRY, *chain, _VAULT, _CONTAINER, _SINK]],
        edges=[
            kit.ek(_ENTRY, EdgeType.ASSUMES, _HEAD),
            *kit.chain_keys(chain, EdgeType.ASSUMES),
            kit.ek(reader, EdgeType.CAN_READ, _VAULT),
            kit.ek(_VAULT, EdgeType.CAN_READ, _CONTAINER),
            kit.ek(_CONTAINER, EdgeType.STORES_SENSITIVE_DATA, _SINK),
        ],
        sink_kind=SinkKind.DATA,
        target=kit.nid(_SINK),
        explanation=(
            "SSRF against App Service queries IMDS for the managed identity token"
            + (f"; {hop_lines(names, _HOP_VERB)}" if len(names) > 1 else "")
            + f"; {names[-1]} reads Key Vault secrets and opens the customer financial container"
        ),
    )
