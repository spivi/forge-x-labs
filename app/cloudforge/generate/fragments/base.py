"""Fragment protocol + registry — the addressable safe-vocabulary.

Each fragment owns its own node ids (namespaced by ``ns``), edges, findings, and
ground-truth paths, so composed artifacts stay self-consistent by construction. A
future learned/diffusion engine decodes into this same registry.
"""

from __future__ import annotations

from collections.abc import Callable
from random import Random
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel, ConfigDict

from app.cloudforge.models.findings import ExpectedFinding, GroundTruthPath
from app.cloudforge.models.graph import GraphEdge, GraphNode


class FragmentBundle(BaseModel):
    """One fragment's owned contribution to a scenario."""

    model_config = ConfigDict(extra="forbid")

    nodes: list[GraphNode]
    edges: list[GraphEdge]
    findings: list[ExpectedFinding]
    paths: list[GroundTruthPath]


class Fragment(Protocol):
    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle: ...


_FragmentT = TypeVar("_FragmentT", bound=type)

_REGISTRY: dict[str, Fragment] = {}


def register(kind: str) -> Callable[[_FragmentT], _FragmentT]:
    def _decorate(cls: _FragmentT) -> _FragmentT:
        _REGISTRY[kind] = cls()
        return cls

    return _decorate


def get_fragment(kind: str) -> Fragment:
    return _REGISTRY[kind]


def all_kinds() -> list[str]:
    return sorted(_REGISTRY)
