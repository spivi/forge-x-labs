"""Fail-soft validation orchestration.

Runs the checks in order, collecting a ``ValidationReport``. Missing optional tools
produce WARN (never change the exit code); only a real check failure sets
``has_failure``. The graph-risk engine always runs (stdlib only).
"""

from __future__ import annotations

from pathlib import Path

from app.cloudforge.generate.base import ScenarioBundle
from app.cloudforge.io.loaders import load_json, load_yaml
from app.cloudforge.io.paths import ScenarioPaths
from app.cloudforge.models.findings import ExpectedFindings, GroundTruthPaths
from app.cloudforge.models.graph import ScenarioGraph
from app.cloudforge.models.scenario import ScenarioSpec
from app.cloudforge.validate import external_scans, scanner_score, schema_checks
from app.cloudforge.validate.graph_risk import GraphRiskEngine
from app.cloudforge.validate.results import Status, ValidationOutcome, ValidationReport

DEFAULT_POLICY_PATH = "policies/scenario.rego"


def run_validations(
    base_dir: Path | str, policy_path: str = DEFAULT_POLICY_PATH
) -> ValidationReport:
    paths = ScenarioPaths.from_dir(base_dir)
    report = ValidationReport()

    report.add(schema_checks.validate_scenario(paths))
    report.add(schema_checks.validate_graph(paths))
    report.add(external_scans.run_terraform(paths))
    report.add(external_scans.run_checkov(paths))
    report.add(_score_scanner(paths))
    report.add(external_scans.run_opa(paths, policy_path))
    report.extend(_run_risk_engine(paths))

    return report


def _score_scanner(paths: ScenarioPaths) -> ValidationOutcome:
    """Score checkov output against expected findings (gap #10). Fail-soft when absent."""
    written = scanner_score.write_scanner_score(paths)
    if written is None:
        return ValidationOutcome(Status.WARN, "scanner score", "not scored — no scanner output")
    score = scanner_score.score_scenario(paths)
    assert score is not None  # write succeeded, so a score exists
    detail = (
        f"{score.matched_findings}/{score.expected_findings} expected findings detected "
        f"(coverage {score.scanner_coverage_score})"
    )
    return ValidationOutcome(Status.PASS, "scanner score", detail)


def _run_risk_engine(paths: ScenarioPaths) -> list:  # type: ignore[type-arg]
    spec = ScenarioSpec.model_validate(load_yaml(paths.scenario_yaml))
    bundle = _load_bundle(paths)
    return GraphRiskEngine(bundle, spec).run()


def _load_bundle(paths: ScenarioPaths) -> ScenarioBundle:
    return ScenarioBundle(
        graph=ScenarioGraph.model_validate(load_json(paths.graph)),
        findings=ExpectedFindings.model_validate(load_json(paths.expected_findings)),
        ground_truth=GroundTruthPaths.model_validate(load_json(paths.ground_truth_paths)),
    )
