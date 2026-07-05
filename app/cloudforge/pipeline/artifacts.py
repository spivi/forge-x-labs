"""Writes the complete scenario output tree from a generated bundle.

The graph is serialized with ``by_alias=True`` so the JSON edge field is ``from``
(a Python keyword), matching what the risk engine and OPA policy expect.
"""

from __future__ import annotations

from app.cloudforge.generate.base import ScenarioBundle
from app.cloudforge.io.loaders import dump_json, dump_yaml
from app.cloudforge.io.paths import ScenarioPaths
from app.cloudforge.models.scenario import ScenarioSpec
from app.cloudforge.pipeline.terraform_emitter import TerraformEmitter


class ScenarioArtifacts:
    """Serializes a scenario spec + generated bundle into the output tree."""

    def __init__(self, paths: ScenarioPaths) -> None:
        self._paths = paths

    def write_all(self, spec: ScenarioSpec, bundle: ScenarioBundle) -> None:
        self._paths.base.mkdir(parents=True, exist_ok=True)
        dump_yaml(self._paths.scenario_yaml, spec.model_dump())
        dump_json(self._paths.graph, bundle.graph.model_dump(by_alias=True))
        dump_json(self._paths.expected_findings, bundle.findings.model_dump())
        dump_json(self._paths.ground_truth_paths, bundle.ground_truth.model_dump())
        TerraformEmitter(bundle.graph).emit(self._paths.terraform_dir)
        self._paths.scanner_results_dir.mkdir(parents=True, exist_ok=True)
