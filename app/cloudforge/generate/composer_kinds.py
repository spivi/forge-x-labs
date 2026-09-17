"""Registry of fragment kinds, variation-axis keys, vendor pools and origins for
GraphComposer.

A fragment kind is ``<family>.<name>``; the family (``core``, ``decoy``,
``false_positive``, ``compensating_control``, ``benign_noise``) is what the
composer stamps into ``GraphNode.origin``. ``SHORT`` maps every kind to the
``variation_axes`` role it counts under (``decoy`` / ``fp`` / ``ctrl`` / ``noise``).

The non-core kinds are grouped into one pool per ``ScenarioSpec.cloud``. The
composer draws every extra and every filler node from ``POOLS[spec.cloud]`` only,
so an Azure estate is padded with Azure resources and a GCP estate with GCP ones.
The Kubernetes family federates into AWS IAM and reads S3, so its pool is its own
cluster-side filler plus the whole AWS pool; ``multi_cloud`` gets every pool.
"""

from __future__ import annotations

from app.cloudforge.generate.fragments.base import core_kind_for, core_scenario_types
from app.cloudforge.models.graph import NodeOrigin

# ``scenario_type`` -> fragment kind, derived from every ``@register_core``
# fragment's own ``scenario_type`` (see ``fragments/base.py``). Adding a family
# means adding its fragment module; this map never gets a hand-written entry.
CORE_KINDS: dict[str, str] = {st: core_kind_for(st) for st in core_scenario_types()}

# The roles the composer plans extras for, in plan order. Each is a ``SHORT`` value
# and a ``variation_axes`` key; the count for a role is per role, whatever vendor
# kind ends up filling it.
EXTRA_ROLES: tuple[str, ...] = ("decoy", "fp", "ctrl")
NOISE_ROLE = "noise"

AWS_NOISE_KINDS: tuple[str, ...] = (
    "benign_noise.unrelated_bucket",
    "benign_noise.sqs_queue",
    "benign_noise.kms_key",
    "benign_noise.iam_role",
    "benign_noise.ecr_repo",
    "benign_noise.data_set",
    "benign_noise.log_trail",
)

AWS_EXTRA_KINDS: tuple[str, ...] = (
    "decoy.iam_role_dead_end",
    "false_positive.public_denied_bucket",
    "compensating_control.explicit_deny",
)

AWS_KINDS: tuple[str, ...] = AWS_NOISE_KINDS + AWS_EXTRA_KINDS

AZURE_KINDS: tuple[str, ...] = (
    "benign_noise.azure_log_container",
    "benign_noise.azure_container_data_set",
    "benign_noise.azure_config_vault",
    "benign_noise.azure_managed_identity",
    "benign_noise.azure_app_service",
    "benign_noise.azure_resource_group",
    "decoy.azure_identity_dead_end",
    "false_positive.azure_private_container",
    "compensating_control.azure_vault_network_rule",
)

GCP_KINDS: tuple[str, ...] = (
    "benign_noise.gcp_artifact_bucket",
    "benign_noise.gcp_bucket_data_set",
    "benign_noise.gcp_service_account",
    "benign_noise.gcp_project",
    "benign_noise.gcp_folder",
    "benign_noise.gcp_workload_identity_pool",
    "decoy.gcp_viewer_dead_end",
    "false_positive.gcp_uniform_access_bucket",
    "compensating_control.gcp_public_access_prevention",
)

K8S_KINDS: tuple[str, ...] = (
    "benign_noise.k8s_namespace_pod",
    "benign_noise.k8s_pod_data_set",
    "benign_noise.k8s_service_account",
    "benign_noise.k8s_cluster",
    "benign_noise.k8s_namespace",
    "decoy.k8s_irsa_dead_end",
)

# One pool per ``ScenarioSpec.cloud`` value. Tuple order is part of the seed
# contract: ``rng.choice`` indexes into it, so reordering a pool changes every
# estate drawn from it.
POOLS: dict[str, tuple[str, ...]] = {
    "aws": AWS_KINDS,
    "azure": AZURE_KINDS,
    "gcp": GCP_KINDS,
    "k8s": K8S_KINDS + AWS_KINDS,
    "multi_cloud": AWS_KINDS + AZURE_KINDS + GCP_KINDS + K8S_KINDS,
}

# ``variation_axes`` keys per kind (``spec.variation_axes["decoy"]`` etc.). These
# are spec vocabulary only; they never appear in a generated id.
SHORT: dict[str, str] = {
    **{kind: "core" for kind in CORE_KINDS.values()},
    "decoy.iam_role_dead_end": "decoy",
    "false_positive.public_denied_bucket": "fp",
    "compensating_control.explicit_deny": "ctrl",
    "benign_noise.unrelated_bucket": "noise",
    "benign_noise.sqs_queue": "noise",
    "benign_noise.kms_key": "noise",
    "benign_noise.iam_role": "noise",
    "benign_noise.ecr_repo": "noise",
    "benign_noise.data_set": "noise",
    "benign_noise.log_trail": "noise",
    "benign_noise.azure_log_container": "noise",
    "benign_noise.azure_container_data_set": "noise",
    "benign_noise.azure_config_vault": "noise",
    "benign_noise.azure_managed_identity": "noise",
    "benign_noise.azure_app_service": "noise",
    "benign_noise.azure_resource_group": "noise",
    "decoy.azure_identity_dead_end": "decoy",
    "false_positive.azure_private_container": "fp",
    "compensating_control.azure_vault_network_rule": "ctrl",
    "benign_noise.gcp_artifact_bucket": "noise",
    "benign_noise.gcp_bucket_data_set": "noise",
    "benign_noise.gcp_service_account": "noise",
    "benign_noise.gcp_project": "noise",
    "benign_noise.gcp_folder": "noise",
    "benign_noise.gcp_workload_identity_pool": "noise",
    "decoy.gcp_viewer_dead_end": "decoy",
    "false_positive.gcp_uniform_access_bucket": "fp",
    "compensating_control.gcp_public_access_prevention": "ctrl",
    "benign_noise.k8s_namespace_pod": "noise",
    "benign_noise.k8s_pod_data_set": "noise",
    "benign_noise.k8s_service_account": "noise",
    "benign_noise.k8s_cluster": "noise",
    "benign_noise.k8s_namespace": "noise",
    "decoy.k8s_irsa_dead_end": "decoy",
}


def kinds_for(cloud: str, role: str) -> tuple[str, ...]:
    """The kinds in ``POOLS[cloud]`` that count under ``role``, in pool order."""
    return tuple(kind for kind in POOLS[cloud] if SHORT[kind] == role)


# Fragment kind family (the part before the first ``.``) -> the ``GraphNode.origin``
# the composer stamps on every node that family builds.
ORIGINS: dict[str, NodeOrigin] = {
    "core": "core",
    "decoy": "decoy",
    "false_positive": "false_positive",
    "compensating_control": "compensating_control",
    "benign_noise": "noise",
}


def origin_of(kind: str) -> NodeOrigin:
    """The origin label for a registered fragment kind such as ``decoy.iam_role_dead_end``."""
    return ORIGINS[kind.split(".", 1)[0]]
