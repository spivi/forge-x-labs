"""Builders shared by the core fragments: the path shape and the pieces of it.

Every core fragment mints namespaced nodes and edges under one fixed tag set and
reads the same shape parameters the composer draws per ``(spec, seed)`` and hands
over in ``params`` (see ``composer.py``):

- ``extra_hops``: intermediate identity hops between the entry's first identity
  and the resource, for the identity-chain families;
- ``prefix_hops``: identity nodes (an application role, optionally a CI identity
  in front of it) on the second route a resource-shaped family adds;
- ``dead_end``: a branch from the entry node that leads nowhere sensitive;
- ``lookalike``: a second resource of the exposed type, equally exposed on its
  face and actually blocked, for the resource-shaped families.

A fragment must build the same node types, in the same count, for the same
params whatever the rng: the composer counts a fragment's size under a throwaway
rng. The rng only picks names from ``_vocab``.

Hop and branch ids are slugs of the names they draw (``role-artifact-promotion``
for ``ArtifactPromotionRole``), the shape every other id has: neither an id nor a
name may say a node is a hop, a dead end or a lookalike.
"""

from __future__ import annotations

import re
from random import Random
from typing import Any, NamedTuple

from app.cloudforge.models.graph import (
    Criticality,
    EdgeRisk,
    EdgeSecurity,
    EdgeType,
    GraphEdge,
    GraphNode,
    NodeSecurity,
    NodeTags,
    NodeType,
)

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


class Shape(NamedTuple):
    """The path shape the composer drew for one estate."""

    extra_hops: int = 0
    prefix_hops: int = 0
    dead_end: bool = False
    lookalike: bool = False


def shape_of(params: dict[str, Any]) -> Shape:
    """The shape in ``params``; every field defaults to the easy, direct chain."""
    return Shape(
        extra_hops=max(0, int(params.get("extra_hops", 0))),
        prefix_hops=max(0, int(params.get("prefix_hops", 0))),
        dead_end=bool(params.get("dead_end", False)),
        lookalike=bool(params.get("lookalike", False)),
    )


def slug(prefix: str, name: str) -> str:
    """``("role", "ArtifactPromotionRole")`` -> ``role-artifact-promotion``;
    ``("id", "id-pipeline-runner")`` -> ``id-pipeline-runner``."""
    stem = _CAMEL_BOUNDARY.sub("-", name).lower()
    stem = stem.removesuffix("-role").removesuffix("-policy").removeprefix(f"{prefix}-")
    return f"{prefix}-{stem}"


class Kit:
    """Namespaced node and edge builders under one fragment's tag set."""

    def __init__(self, ns: str, tags: NodeTags) -> None:
        self._ns = ns
        self._tags = tags

    def nid(self, node_id: str) -> str:
        return f"{self._ns}/{node_id}" if self._ns else node_id

    def bare(self, node: GraphNode) -> str:
        """The fragment-local id of a node built by this kit."""
        return node.id.removeprefix(f"{self._ns}/") if self._ns else node.id

    def node(
        self,
        node_id: str,
        ntype: NodeType,
        name: str,
        crit: Criticality,
        **attrs: str | list[str],
    ) -> GraphNode:
        return GraphNode(
            id=self.nid(node_id),
            type=ntype,
            name=name,
            tags=self._tags,
            security=NodeSecurity(criticality=crit),
            attributes=dict(attrs),
        )

    def edge(self, src: str, dst: str, etype: EdgeType, risk: EdgeRisk) -> GraphEdge:
        return GraphEdge(
            from_=self.nid(src), to=self.nid(dst), type=etype, security=EdgeSecurity(risk=risk)
        )

    def ek(self, src: str, etype: EdgeType, dst: str) -> str:
        """The ground-truth edge key ``from->type->to``."""
        return f"{self.nid(src)}->{etype.value}->{self.nid(dst)}"

    def chain(self, ids: list[str], etype: EdgeType, risk: EdgeRisk) -> list[GraphEdge]:
        """One edge per consecutive pair of ``ids``."""
        return [self.edge(a, b, etype, risk) for a, b in zip(ids, ids[1:], strict=False)]

    def chain_keys(self, ids: list[str], etype: EdgeType) -> list[str]:
        return [self.ek(a, etype, b) for a, b in zip(ids, ids[1:], strict=False)]


class Piece(NamedTuple):
    """Nodes and edges difficulty adds next to the path (a branch, a lookalike)."""

    nodes: list[GraphNode]
    edges: list[GraphEdge]


class Hops(NamedTuple):
    """Drawn intermediate identities: their bare ids, names and nodes."""

    ids: list[str]
    names: list[str]
    nodes: list[GraphNode]


def draw_hops(
    kit: Kit,
    rng: Random,
    count: int,
    vocab: tuple[str, ...],
    prefix: str,
    ntype: NodeType,
    crit: Criticality = "high",
    **attrs: str | list[str],
) -> Hops:
    """``count`` identity nodes with distinct names drawn from ``vocab``.

    The count comes from the composer, never from the rng, so the fragment's
    size is the same under any rng; only which names are used varies."""
    names = rng.sample(vocab, count) if count else []
    ids = [slug(prefix, name) for name in names]
    pairs = zip(ids, names, strict=True)
    nodes = [kit.node(nid, ntype, name, crit, **attrs) for nid, name in pairs]
    return Hops(ids=ids, names=names, nodes=nodes)


def hop_lines(names: list[str], verb: str) -> str:
    """One finding line per hop for the explanation: ``A assumes B; B assumes C``."""
    return "; ".join(f"{a} {verb} {b}" for a, b in zip(names, names[1:], strict=False))
