"""Canned scenario registry."""

from __future__ import annotations

from collections.abc import Callable

from lemmings.scenarios import (
    budget_exhausted,
    happy_path,
    merge_order_conflict,
    review_loop,
)
from lemmings.sim.scenario import Scenario

REGISTRY: dict[str, Callable[[], Scenario]] = {
    "budget_exhausted": budget_exhausted.build,
    "review_loop": review_loop.build,
    "merge_order_conflict": merge_order_conflict.build,
    "happy_path": happy_path.build,
}


def all_names() -> list[str]:
    return sorted(REGISTRY)


def get(name: str) -> Scenario:
    if name not in REGISTRY:
        raise KeyError(f"unknown scenario {name!r}; available: {all_names()}")
    return REGISTRY[name]()


__all__ = ["REGISTRY", "all_names", "get"]
