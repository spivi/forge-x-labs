"""The access-granting hop of a path: what opens the way.

A path is graded on three things, in order: where it starts (the entry, the
first node), what opens the way (the hop) and what the attacker reaches (the
target, the last node). The hop is the first identity after the entry; when the
path has none (a public bucket, a shared snapshot, a wildcard queue) it is the
exposed resource, the first middle node; a two-node path has neither, and the
sink itself is what opens the way. ``access_hop`` applies that rule from node
types; ``positional_hop`` is what a reader without types (an old grade key)
falls back to, and on every shipped family it lands on the same node: the
second one.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from app.cloudforge.models.graph import NodeType

IDENTITY_TYPES: frozenset[NodeType] = frozenset(
    {
        NodeType.IAM_ROLE,
        NodeType.CICD_IDENTITY,
        NodeType.K8S_SERVICE_ACCOUNT,
        NodeType.AZURE_MANAGED_IDENTITY,
        NodeType.GCP_SERVICE_ACCOUNT,
        NodeType.GCP_WORKLOAD_IDENTITY_POOL,
    }
)


def access_hop(nodes: Sequence[str], type_of: Mapping[str, NodeType]) -> str:
    """The first identity after the entry, else the exposed resource (the first
    middle node), else the last node."""
    middle = nodes[1:-1]
    for node_id in middle:
        if type_of.get(node_id) in IDENTITY_TYPES:
            return node_id
    if middle:
        return middle[0]
    return nodes[-1]


def positional_hop(nodes: Sequence[str]) -> str:
    """The hop a reader picks without node types: the second node, which is the
    first identity of a chain, the exposed resource of a three-node path and the
    sink of a two-node one."""
    return nodes[1] if len(nodes) > 1 else nodes[0]
