"""The generator interface + the bundle every generator returns.

A generator turns a validated ``ScenarioSpec`` into a self-consistent bundle: the
risk graph plus its ground-truth paths and expected findings.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict

from app.cloudforge.models.findings import ExpectedFindings, GroundTruthPaths
from app.cloudforge.models.graph import ScenarioGraph
from app.cloudforge.models.scenario import ScenarioSpec


class ScenarioBundle(BaseModel):
    """Everything a generator produces for one scenario."""

    model_config = ConfigDict(extra="forbid")

    graph: ScenarioGraph
    findings: ExpectedFindings
    ground_truth: GroundTruthPaths


class ScenarioGenerator(Protocol):
    """Any engine that turns a scenario spec into a validated bundle."""

    def generate(self, spec: ScenarioSpec) -> ScenarioBundle:
        """Return a graph + ground truth consistent with ``spec``."""
        ...
