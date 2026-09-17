"""Kubernetes non-core fragments: the ``k8s`` pool's own noise and decoy.

The Kubernetes family federates into AWS IAM and reads S3, so the composer gives
a ``k8s`` estate this pool plus the whole AWS pool; AWS roles, buckets and queues
are legitimate next to the cluster. What this module adds is the cluster-side
filler: a namespace with a pod, a service account with no cloud annotation, a
second cluster, a bare namespace, and a decoy service account whose IAM role
can do operational things but reaches no data. ``K8sNamespace``, ``K8sPod`` and
``K8sServiceAccount`` have Terraform blocks; ``K8sCluster`` is placed by the core
fragment already and has a workbench zone.

Ids and names come from ``_vocab`` and never say what a fragment is for; the
composer records that in ``GraphNode.origin``. Edges are benign and no fragment
here owns a ground-truth path.
"""

from __future__ import annotations

from random import Random
from typing import Any

from app.cloudforge.generate.fragments._noncore import bundle, draw_tags, edge, node
from app.cloudforge.generate.fragments._vocab import (
    K8S_BARE_NAMESPACES,
    K8S_CLUSTERS,
    K8S_DECOY_BINDINGS,
    K8S_NAMESPACE_PODS,
    K8S_PLAIN_SERVICE_ACCOUNTS,
)
from app.cloudforge.generate.fragments.base import FragmentBundle, register
from app.cloudforge.models.graph import EdgeType, NodeType

_ACCOUNT_ID = "123456789012"
_OIDC = "https://oidc.eks.us-east-1.amazonaws.com/id/EXAMPLED3B761B01042F"


@register("benign_noise.k8s_namespace_pod")
class K8sNamespacePod:
    """A namespace with one pod in it."""

    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        tags = draw_tags(rng)
        namespace_name, pod_name = rng.choice(K8S_NAMESPACE_PODS)
        namespace = node(
            ns, namespace_name, NodeType.K8S_NAMESPACE, tags, namespace=namespace_name
        )
        pod = node(
            ns,
            pod_name,
            NodeType.K8S_POD,
            tags,
            namespace=namespace_name,
            service_account="default",
        )
        return bundle([namespace, pod], [edge(pod, namespace, EdgeType.IN_NAMESPACE)])


@register("benign_noise.k8s_service_account")
class K8sPlainServiceAccount:
    """A service account with no cloud annotation at all."""

    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        name = rng.choice(K8S_PLAIN_SERVICE_ACCOUNTS)
        return bundle(
            [
                node(
                    ns,
                    name,
                    NodeType.K8S_SERVICE_ACCOUNT,
                    draw_tags(rng),
                    namespace="workloads",
                    automount_token="false",
                )
            ]
        )


@register("benign_noise.k8s_cluster")
class K8sSecondCluster:
    """A second cluster next to the one on the path."""

    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        name, issuer = rng.choice(K8S_CLUSTERS)
        return bundle([node(ns, name, NodeType.K8S_CLUSTER, draw_tags(rng), oidc_issuer=issuer)])


@register("benign_noise.k8s_namespace")
class K8sBareNamespace:
    """A namespace with nothing of interest in it."""

    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        name = rng.choice(K8S_BARE_NAMESPACES)
        return bundle([node(ns, name, NodeType.K8S_NAMESPACE, draw_tags(rng), namespace=name)])


@register("decoy.k8s_irsa_dead_end")
class K8sIrsaDeadEnd:
    """A service account annotated to an IAM role that has no data access: the
    IRSA hop of the core path, leading to a role that reads nothing."""

    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        tags = draw_tags(rng)
        sa_name, role_name, actions = rng.choice(K8S_DECOY_BINDINGS)
        role_arn = f"arn:aws:iam::{_ACCOUNT_ID}:role/{role_name}"
        account = node(
            ns,
            sa_name,
            NodeType.K8S_SERVICE_ACCOUNT,
            tags,
            "medium",
            namespace="workloads",
            annotations=[f"eks.amazonaws.com/role-arn: {role_arn}"],
            role_arn=role_arn,
        )
        role = node(
            ns,
            role_name,
            NodeType.IAM_ROLE,
            tags,
            "medium",
            oidc_provider=_OIDC,
            trust_policy=f"Federated: {_OIDC}",
            actions=list(actions),
        )
        return bundle([account, role], [edge(account, role, EdgeType.FEDERATES_TO)])
