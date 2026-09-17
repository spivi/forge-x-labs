"""Azure non-core fragments: the ``azure`` pool's noise, decoy, false positive and
compensating control.

Every node type here is one the Azure Terraform emitter renders and the workbench
zones already place (``AzureStorageContainer``, ``AzureKeyVault``,
``AzureManagedIdentity``, ``AzureAppService``, ``AzureResourceGroup``). A role
assignment would be the natural fifth noise kind, but ``AzureRoleAssignment`` has
neither an emitter block nor a workbench zone, so the assignment is carried as
attributes on the identity that holds it and the fifth noise kind is a resource
group instead.

Ids and names come from ``_vocab`` and never say what a fragment is for; the
composer records that in ``GraphNode.origin``. Edges are benign and no fragment
here owns a ground-truth path.
"""

from __future__ import annotations

from random import Random
from typing import Any

from app.cloudforge.generate.fragments._noncore import bundle, draw_tags, edge, node
from app.cloudforge.generate.fragments._vocab import (
    AZURE_APP_NAMES,
    AZURE_CONFIG_VAULTS,
    AZURE_DECOY_IDENTITIES,
    AZURE_IDENTITY_NAMES,
    AZURE_LOCKED_VAULTS,
    AZURE_LOG_CONTAINERS,
    AZURE_PUBLIC_LOOKING_CONTAINERS,
    AZURE_RESOURCE_GROUPS,
)
from app.cloudforge.generate.fragments.base import FragmentBundle, register
from app.cloudforge.models.findings import ExpectedFinding, FindingFamily
from app.cloudforge.models.graph import EdgeType, NodeType

_LOCATION = "eastus"
_RESOURCE_GROUP = "rg-workloads"


@register("benign_noise.azure_log_container")
class AzureLogContainer:
    """A storage container an app writes its logs to."""

    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        name, account = rng.choice(AZURE_LOG_CONTAINERS)
        return bundle(
            [
                node(
                    ns,
                    name,
                    NodeType.AZURE_STORAGE_CONTAINER,
                    draw_tags(rng),
                    storage_account=account,
                    access_type="private",
                )
            ]
        )


@register("benign_noise.azure_config_vault")
class AzureConfigVault:
    """A key vault holding an app's configuration."""

    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        name = rng.choice(AZURE_CONFIG_VAULTS)
        return bundle(
            [
                node(
                    ns,
                    name,
                    NodeType.AZURE_KEY_VAULT,
                    draw_tags(rng),
                    sku="standard",
                    purge_protection="true",
                    resource_group_name=_RESOURCE_GROUP,
                )
            ]
        )


@register("benign_noise.azure_managed_identity")
class AzureMonitoringIdentity:
    """A user-assigned identity a monitoring app service runs as."""

    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        name = rng.choice(AZURE_IDENTITY_NAMES)
        return bundle(
            [
                node(
                    ns,
                    name,
                    NodeType.AZURE_MANAGED_IDENTITY,
                    draw_tags(rng),
                    identity_type="UserAssigned",
                    role_definition="Monitoring Reader",
                    resource_group_name=_RESOURCE_GROUP,
                )
            ]
        )


@register("benign_noise.azure_app_service")
class AzureInternalApp:
    """An app service for an internal tool."""

    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        name = rng.choice(AZURE_APP_NAMES)
        return bundle(
            [
                node(
                    ns,
                    name,
                    NodeType.AZURE_APP_SERVICE,
                    draw_tags(rng),
                    identity_type="SystemAssigned",
                    https_only="true",
                )
            ]
        )


@register("benign_noise.azure_resource_group")
class AzureResourceGroupNoise:
    """A resource group with its own scoped assignment, carried as attributes."""

    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        name = rng.choice(AZURE_RESOURCE_GROUPS)
        return bundle(
            [
                node(
                    ns,
                    name,
                    NodeType.AZURE_RESOURCE_GROUP,
                    draw_tags(rng),
                    location=_LOCATION,
                    role_definition="Reader",
                    role_scope="resource_group",
                )
            ]
        )


@register("decoy.azure_identity_dead_end")
class AzureIdentityDeadEnd:
    """A managed identity whose Storage Blob Data Reader assignment reaches a
    container that holds nothing sensitive: the shape of the core path, no sink."""

    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        tags = draw_tags(rng)
        identity_name, container_name, account = rng.choice(AZURE_DECOY_IDENTITIES)
        identity = node(
            ns,
            identity_name,
            NodeType.AZURE_MANAGED_IDENTITY,
            tags,
            "medium",
            identity_type="UserAssigned",
            role_definition="Storage Blob Data Reader",
            role_scope=container_name,
            resource_group_name=_RESOURCE_GROUP,
        )
        container = node(
            ns,
            container_name,
            NodeType.AZURE_STORAGE_CONTAINER,
            tags,
            storage_account=account,
            access_type="private",
        )
        return bundle([identity, container], [edge(identity, container, EdgeType.CAN_READ)])


@register("false_positive.azure_private_container")
class AzurePrivateContainer:
    """A container named like something served to the internet whose public access
    is disabled: a scanner keying on the name alone would be wrong."""

    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        container_name, account = rng.choice(AZURE_PUBLIC_LOOKING_CONTAINERS)
        container = node(
            ns,
            container_name,
            NodeType.AZURE_STORAGE_CONTAINER,
            draw_tags(rng),
            storage_account=account,
            access_type="private",
            allow_blob_public_access="false",
        )
        finding = ExpectedFinding(
            id=f"{ns}/find-fp-azure-01",
            severity="low",
            family=FindingFamily.PUBLIC_LOOKING_BUCKET_WITH_COMPENSATING_CONTROL,
            resource_ids=[container.id],
            expected_scanner_visibility="visible",
            ground_truth="benign",
            remediation=(
                "None needed: the storage account disallows blob public access and the "
                "container is private despite its public-looking name."
            ),
        )
        return bundle([container], findings=[finding])


@register("compensating_control.azure_vault_network_rule")
class AzureVaultNetworkRule:
    """A key vault reachable only through its private endpoint: the network rule
    denies public access, so whatever appears to reach it cannot."""

    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        name = rng.choice(AZURE_LOCKED_VAULTS)
        return bundle(
            [
                node(
                    ns,
                    name,
                    NodeType.AZURE_KEY_VAULT,
                    draw_tags(rng),
                    sku="premium",
                    purge_protection="true",
                    resource_group_name=_RESOURCE_GROUP,
                    public_network_access="Disabled",
                    network_default_action="Deny",
                    private_endpoint="true",
                )
            ]
        )
