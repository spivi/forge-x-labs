"""Per-node id minting for ``GraphComposer``.

Fragments build under a private namespace so their own edges, findings and
ground-truth paths line up by construction. That namespace groups nodes by
fragment, and the grouping is itself an answer: sort the ids and the core path
is the one big cluster. So once a scenario is assembled every node is re-keyed
to ``n<k>_<salt>/<slug>`` where ``k`` comes from a seeded permutation over ALL
nodes (its own stream, ``seed + 307``), and every reference (edge endpoints,
path node ids, path edge keys, path target and hop, finding resource ids) is
rewritten through the same map. The map must be total and unique; a dangling reference raises
``GraphIntegrityError`` before any artifact is written. Path ids and finding
ids keep the fragment prefix: they name no node and never reach the student.
"""

from __future__ import annotations

from random import Random

from app.cloudforge.errors import GraphIntegrityError
from app.cloudforge.generate.fragments.base import FragmentBundle

_EDGE_KEY_PARTS = 3


def node_ns(token: int, salt: str) -> str:
    return f"n{token:02d}_{salt}" if salt else f"n{token:02d}"


def retoken(bundle: FragmentBundle, seed: int, salt: str) -> FragmentBundle:
    """Give every node its own token and rewrite all references in place."""
    tokens = list(range(len(bundle.nodes)))
    Random(seed + 307).shuffle(tokens)
    mapping: dict[str, str] = {}
    for node, token in zip(bundle.nodes, tokens, strict=True):
        slug = node.id.split("/", 1)[-1]
        mapping[node.id] = f"{node_ns(token, salt)}/{slug}"
    if len(set(mapping.values())) != len(mapping):
        raise GraphIntegrityError("per-node tokens produced a duplicate id")
    for node in bundle.nodes:
        node.id = mapping[node.id]
    for edge in bundle.edges:
        edge.from_ = _renamed(mapping, edge.from_)
        edge.to = _renamed(mapping, edge.to)
    for finding in bundle.findings:
        finding.resource_ids = [_renamed(mapping, rid) for rid in finding.resource_ids]
    for path in bundle.paths:
        path.nodes = [_renamed(mapping, nid) for nid in path.nodes]
        path.edges = [_renamed_edge_key(mapping, key) for key in path.edges]
        path.target = _renamed(mapping, path.target)
        if path.hop is not None:
            path.hop = _renamed(mapping, path.hop)
    return bundle


def _renamed(mapping: dict[str, str], ref: str) -> str:
    try:
        return mapping[ref]
    except KeyError:
        raise GraphIntegrityError(f"reference to unknown composed node id: {ref}") from None


def _renamed_edge_key(mapping: dict[str, str], key: str) -> str:
    parts = key.split("->")
    if len(parts) != _EDGE_KEY_PARTS:
        raise GraphIntegrityError(f"malformed ground-truth edge key: {key}")
    src, edge_type, dst = parts
    return f"{_renamed(mapping, src)}->{edge_type}->{_renamed(mapping, dst)}"
