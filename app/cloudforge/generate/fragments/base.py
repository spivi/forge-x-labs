"""Fragment protocol + registry — the addressable safe-vocabulary.

Each fragment owns its own node ids (namespaced by ``ns``), edges, findings, and
ground-truth paths, so composed artifacts stay self-consistent by construction. A
future learned/diffusion engine decodes into this same registry.

A *core* fragment additionally declares a small surface (``scenario_type``,
``cloud``, ``prompt``, ``checklist``, ``teaching_point``) and registers with
``@register_core`` instead of ``@register``. That surface is the single source
every other hand-maintained registration point (the composer's scenario_type ->
kind map, the student brief prompt, the workbench checklist row, the README/wiki
teaching-point table) now derives from, so adding a family is: drop one fragment
module in this package, add one example spec, done.
"""

from __future__ import annotations

from collections.abc import Callable
from random import Random
from typing import Any, NamedTuple, Protocol, TypeVar

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


class CoreMeta(NamedTuple):
    """What a core fragment declares about itself, read back by every derived map."""

    kind: str
    cloud: str
    prompt: str
    checklist: tuple[str, str]
    teaching_point: str


_CORE_ATTRS: tuple[str, ...] = ("scenario_type", "cloud", "prompt", "checklist", "teaching_point")
_CORE_META: dict[str, CoreMeta] = {}


def register_core(cls: _FragmentT) -> _FragmentT:
    """Register a core fragment under ``core.<scenario_type>`` and index its
    declared surface by ``scenario_type`` for ``core_meta``/``core_scenario_types``.

    Raises ``TypeError`` at import time if the class is missing any of the
    declared attributes, so a family that forgets one fails loudly rather than
    silently missing a row in the derived maps.
    """
    for attr in _CORE_ATTRS:
        if not getattr(cls, attr, None):
            raise TypeError(f"{cls.__name__} must set {attr!r} to use @register_core")
    scenario_type = str(cls.scenario_type)  # type: ignore[attr-defined]
    checklist = cls.checklist  # type: ignore[attr-defined]
    if not (isinstance(checklist, tuple) and len(checklist) == 2):
        raise TypeError(f"{cls.__name__}.checklist must be a (finding_id, label) tuple")
    kind = f"core.{scenario_type}"
    _REGISTRY[kind] = cls()
    _CORE_META[scenario_type] = CoreMeta(
        kind=kind,
        cloud=str(cls.cloud),  # type: ignore[attr-defined]
        prompt=str(cls.prompt),  # type: ignore[attr-defined]
        checklist=(str(checklist[0]), str(checklist[1])),
        teaching_point=str(cls.teaching_point),  # type: ignore[attr-defined]
    )
    return cls


def core_scenario_types() -> tuple[str, ...]:
    """Every registered core family's ``scenario_type``, sorted."""
    return tuple(sorted(_CORE_META))


def core_kind_for(scenario_type: str) -> str:
    """The fragment kind (``core.<scenario_type>``) for a registered family."""
    return _CORE_META[scenario_type].kind


def core_meta(scenario_type: str) -> CoreMeta:
    """The declared surface of a registered core family."""
    return _CORE_META[scenario_type]
