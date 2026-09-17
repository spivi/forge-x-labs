"""Azure Terraform blocks compiled from the risk graph. Never applied."""

from __future__ import annotations

from app.cloudforge import constants
from app.cloudforge.models.graph import GraphNode, NodeType
from app.cloudforge.pipeline.identifiers import resource_name
from app.cloudforge.pipeline.terraform_resource_blocks import hcl_str

_EMPTY = constants.EMPTY_TF_HEADER
_TENANT = "00000000-0000-0000-0000-000000000000"


def _attr(node: GraphNode, key: str, default: str) -> str:
    val = node.attributes.get(key, default)
    return val if isinstance(val, str) else default


def resource_group_block(node: GraphNode) -> str:
    ref = resource_name(node)
    loc = hcl_str(_attr(node, "location", "eastus"))
    return "\n".join(
        [
            f'resource "azurerm_resource_group" "{ref}" {{',
            f"  name     = {hcl_str(node.name)}",
            f"  location = {loc}",
            "  tags     = local.common_tags",
            "}",
            "",
        ]
    )


def managed_identity_block(node: GraphNode) -> str:
    ref = resource_name(node)
    rg = hcl_str(_attr(node, "resource_group_name", "rg-workloads"))
    loc = hcl_str(_attr(node, "location", "eastus"))
    return "\n".join(
        [
            f'resource "azurerm_user_assigned_identity" "{ref}" {{',
            f"  name                = {hcl_str(node.name)}",
            f"  resource_group_name = {rg}",
            f"  location            = {loc}",
            "}",
            "",
        ]
    )


def key_vault_block(node: GraphNode) -> str:
    ref = resource_name(node)
    rg = hcl_str(_attr(node, "resource_group_name", "rg-workloads"))
    loc = hcl_str(_attr(node, "location", "eastus"))
    sku = hcl_str(_attr(node, "sku", "standard"))
    purge = "true" if _attr(node, "purge_protection", "false") == "true" else "false"
    lines = [
        f'resource "azurerm_key_vault" "{ref}" {{',
        f"  name                       = {hcl_str(node.name)}",
        f"  location                   = {loc}",
        f"  resource_group_name        = {rg}",
        f'  tenant_id                  = "{_TENANT}"',
        f"  sku_name                   = {sku}",
        f"  purge_protection_enabled   = {purge}",
        "  soft_delete_retention_days = 7",
    ]
    lines += _key_vault_network_lines(node)
    return "\n".join([*lines, "}", ""])


def _key_vault_network_lines(node: GraphNode) -> list[str]:
    """The network rule a vault declares in its attributes, if any: a vault with
    public access disabled and a ``Deny`` default action is reachable only through
    its private endpoint, which is the compensating control the graph models."""
    lines: list[str] = []
    if _attr(node, "public_network_access", "Enabled") == "Disabled":
        lines.append("  public_network_access_enabled = false")
    action = _attr(node, "network_default_action", "")
    if action in ("Allow", "Deny"):
        lines += [
            "  network_acls {",
            f"    default_action = {hcl_str(action)}",
            '    bypass         = "AzureServices"',
            "  }",
        ]
    return lines


def storage_container_block(node: GraphNode) -> str:
    ref = resource_name(node)
    account = _attr(node, "storage_account", "stcloudforge")
    access = _attr(node, "access_type", "private")
    acct_ref = f"{ref}_acct"
    account_lines = [
        f'resource "azurerm_storage_account" "{acct_ref}" {{',
        f"  name                     = {hcl_str(account)}",
        '  resource_group_name      = "rg-workloads"',
        '  location                 = "eastus"',
        '  account_tier             = "Standard"',
        '  account_replication_type = "LRS"',
    ]
    # A container that disallows blob public access at the account level is the
    # false-positive shape: public-looking name, no anonymous read possible.
    if _attr(node, "allow_blob_public_access", "true") == "false":
        account_lines.append("  allow_nested_items_to_be_public = false")
    return "\n".join(
        [
            *account_lines,
            "}",
            f'resource "azurerm_storage_container" "{ref}" {{',
            f"  name                  = {hcl_str(node.name)}",
            f"  storage_account_name  = azurerm_storage_account.{acct_ref}.name",
            f"  container_access_type = {hcl_str(access)}",
            "}",
            "",
        ]
    )


def app_service_block(node: GraphNode) -> str:
    ref = resource_name(node)
    ident = _attr(node, "identity_type", "SystemAssigned")
    return "\n".join(
        [
            f'resource "azurerm_service_plan" "{ref}_plan" {{',
            f"  name                = {hcl_str(node.name + '-plan')}",
            '  resource_group_name = "rg-workloads"',
            '  location            = "eastus"',
            '  os_type             = "Linux"',
            '  sku_name            = "B1"',
            "}",
            f'resource "azurerm_linux_web_app" "{ref}" {{',
            f"  name                = {hcl_str(node.name)}",
            '  resource_group_name = "rg-workloads"',
            '  location            = "eastus"',
            f"  service_plan_id     = azurerm_service_plan.{ref}_plan.id",
            "  site_config {}",
            "  identity {",
            f"    type = {hcl_str(ident)}",
            "  }",
            "}",
            "",
        ]
    )


_BUILDERS = {
    NodeType.AZURE_RESOURCE_GROUP: resource_group_block,
    NodeType.AZURE_MANAGED_IDENTITY: managed_identity_block,
    NodeType.AZURE_KEY_VAULT: key_vault_block,
    NodeType.AZURE_STORAGE_CONTAINER: storage_container_block,
    NodeType.AZURE_APP_SERVICE: app_service_block,
}


def build_azure_tf(nodes: list[GraphNode]) -> str:
    blocks = [_BUILDERS[n.type](n) for n in nodes if n.type in _BUILDERS]
    return "".join(blocks) if blocks else _EMPTY
