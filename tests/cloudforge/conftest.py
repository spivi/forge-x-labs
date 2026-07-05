"""Shared fixtures for the cloudforge product test-suite.

``generated_scenario`` runs the real generator once into a temp dir so validate /
report tests exercise the same artifact tree the CLI produces.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.cloudforge.generate.template_generator import TemplateGenerator
from app.cloudforge.io.loaders import load_yaml
from app.cloudforge.io.paths import ScenarioPaths
from app.cloudforge.models.scenario import ScenarioSpec
from app.cloudforge.pipeline.artifacts import ScenarioArtifacts

EXAMPLE_SCENARIO = Path("examples/ci_cd_iam_chain.yaml")


@pytest.fixture
def example_spec() -> ScenarioSpec:
    return ScenarioSpec.model_validate(load_yaml(EXAMPLE_SCENARIO))


@pytest.fixture
def generated_scenario(tmp_path: Path, example_spec: ScenarioSpec) -> Path:
    bundle = TemplateGenerator().generate(example_spec)
    out = tmp_path / "scenario_001"
    ScenarioArtifacts(ScenarioPaths.from_dir(out)).write_all(example_spec, bundle)
    return out
