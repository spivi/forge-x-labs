"""Schema validation for the on-disk scenario + graph artifacts.

Re-loads the written files and validates them against the same Pydantic models used
to generate them, so a hand-edited artifact tree is caught.
"""

from __future__ import annotations

from pydantic import ValidationError

from app.cloudforge.errors import ScenarioLoadError
from app.cloudforge.io.loaders import load_json, load_yaml
from app.cloudforge.io.paths import ScenarioPaths
from app.cloudforge.models.graph import ScenarioGraph
from app.cloudforge.models.scenario import ScenarioSpec
from app.cloudforge.validate.results import Status, ValidationOutcome


def validate_scenario(paths: ScenarioPaths) -> ValidationOutcome:
    return _validate(paths.scenario_yaml, load_yaml, ScenarioSpec, "scenario schema valid")


def validate_graph(paths: ScenarioPaths) -> ValidationOutcome:
    return _validate(paths.graph, load_json, ScenarioGraph, "graph schema valid")


def _validate(path, loader, model, label: str) -> ValidationOutcome:  # type: ignore[no-untyped-def]
    try:
        model.model_validate(loader(path))
    except ScenarioLoadError as exc:
        return ValidationOutcome(Status.FAIL, label, str(exc))
    except ValidationError as exc:
        return ValidationOutcome(Status.FAIL, label, f"{exc.error_count()} schema error(s)")
    return ValidationOutcome(Status.PASS, label)
