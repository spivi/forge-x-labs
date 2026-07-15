"""Expands a suite-level ``VariationSpec`` into concrete per-scenario ``ScenarioSpec``s.

``VariationSpec.variation_axes`` is a *sweep* (``{"decoy": ["0", "1", "2"]}``);
``ScenarioSpec.variation_axes`` is *concrete* (``{"decoy": "1"}``). The axis value
for a given seed is chosen by ``seed % len(values)`` — a pure function of the seed,
so expansion never draws from any RNG and stays byte-reproducible (design doc §6).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.cloudforge.io.loaders import load_yaml
from app.cloudforge.models.scenario import ScenarioSpec
from app.cloudforge.variation.models import VariationSpec

_EXAMPLES_DIR = Path("examples")


@dataclass(frozen=True)
class ScenarioUnit:
    """One concrete (family, scale, seed) cell of the suite's sweep."""

    scenario_id: str
    family: str
    seed: int
    scale: str
    spec: ScenarioSpec


def expand(variation_spec: VariationSpec) -> list[ScenarioUnit]:
    """Return one ``ScenarioUnit`` per (family x scale x seed) cell, in a stable,
    deterministic order (families, then scales, then seeds — all as declared)."""
    units: list[ScenarioUnit] = []
    seeds = range(variation_spec.seed_start, variation_spec.seed_start + variation_spec.seed_count)
    for family in variation_spec.families:
        for scale in variation_spec.scale_profiles:
            for seed in seeds:
                units.append(_build_unit(variation_spec, family, scale, seed))
    return units


def _build_unit(variation_spec: VariationSpec, family: str, scale: str, seed: int) -> ScenarioUnit:
    axes = _select_axes(variation_spec.variation_axes, seed)
    base = _load_base_spec(family)
    spec = base.model_copy(update={"scale_profile": scale, "variation_axes": axes})
    scenario_id = f"{family}-{scale}-seed{seed}"
    return ScenarioUnit(scenario_id=scenario_id, family=family, seed=seed, scale=scale, spec=spec)


def _select_axes(sweep: dict[str, list[str]], seed: int) -> dict[str, str]:
    return {axis: values[seed % len(values)] for axis, values in sweep.items() if values}


def _load_base_spec(family: str) -> ScenarioSpec:
    data = load_yaml(_EXAMPLES_DIR / f"{family}.yaml")
    data.setdefault("scale_profile", "small")
    data.setdefault("variation_axes", {})
    return ScenarioSpec.model_validate(data)


__all__ = ["ScenarioUnit", "expand"]
