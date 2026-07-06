"""Assembles ``report.md`` from on-disk scenario artifacts.

Report works standalone: it re-loads the spec, graph, findings, and ground truth
(plus optional scanner/OPA results) from the output tree and joins the section
builders. This decouples reporting from the in-memory generate/validate state.

To honor clause S15 (a report must never render false success for a FAILed
scenario), the renderer re-runs the deterministic, stdlib-only validation
(``run_local_validations``: schema + graph-risk engine — no external scanner
subprocesses, no network, no side effects) over the same on-disk artifacts and
surfaces the outcome in a ``## Validation`` section near the top. It is run
fail-soft: if it cannot run (a corrupt/missing artifact), the report says so
rather than implying the scenario passed. The optional external scanners
(terraform/checkov/opa) keep their own existing report sections and are never
invoked from here.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from app.cloudforge.errors import CloudforgeError
from app.cloudforge.generate.base import ScenarioBundle
from app.cloudforge.io.loaders import load_json, load_yaml, write_text
from app.cloudforge.io.paths import ScenarioPaths
from app.cloudforge.models.findings import ExpectedFindings, GroundTruthPaths
from app.cloudforge.models.graph import ScenarioGraph
from app.cloudforge.models.scenario import ScenarioSpec
from app.cloudforge.report import sections
from app.cloudforge.validate.orchestrator import run_local_validations
from app.cloudforge.validate.results import ValidationReport
from app.cloudforge.validate.scanner_score import score_scenario


class ReportRenderer:
    """Renders a Markdown report for one scenario directory."""

    def __init__(self, base_dir: Path | str) -> None:
        self._paths = ScenarioPaths.from_dir(base_dir)

    def render(self) -> str:
        spec = ScenarioSpec.model_validate(load_yaml(self._paths.scenario_yaml))
        bundle = self._load_bundle()
        validation = self._run_validation()
        integrity_failed = sections.path_integrity_failed(validation)
        checkov_ok = self._paths.checkov_results.exists()
        opa_ok = self._paths.opa_results.exists()
        blocks = [
            sections.build_title(spec),
            sections.build_banner(),
            sections.build_validation(validation),
            sections.build_summary(spec),
            sections.build_resources(bundle),
            sections.build_findings(bundle),
            sections.build_critical_path(bundle, integrity_failed=integrity_failed),
            sections.build_scanner_summary(
                checkov_ok, "checkov results present in scanner_results/."
            ),
            sections.build_scanner_score(score_scenario(self._paths)),
            sections.build_opa_summary(opa_ok, "OPA results present in opa_results.json."),
            sections.build_remediation(bundle),
            sections.build_limitations(),
        ]
        return "\n\n".join(blocks) + "\n"

    def _run_validation(self) -> ValidationReport | None:
        """Re-run the deterministic local validation over the on-disk artifacts.

        Fail-soft (clause S15): returns the ``ValidationReport``, or ``None`` if it
        could not run (a missing/corrupt artifact) — the report then explicitly
        declines to claim success rather than crashing or implying a pass. Uses
        :func:`run_local_validations` so rendering a report never spawns
        terraform/checkov/opa subprocesses or touches the network.
        """
        try:
            return run_local_validations(self._paths.base)
        except (CloudforgeError, ValidationError, OSError, ValueError):
            return None

    def render_to_file(self) -> Path:
        write_text(self._paths.report, self.render())
        return self._paths.report

    def _load_bundle(self) -> ScenarioBundle:
        return ScenarioBundle(
            graph=ScenarioGraph.model_validate(load_json(self._paths.graph)),
            findings=ExpectedFindings.model_validate(load_json(self._paths.expected_findings)),
            ground_truth=GroundTruthPaths.model_validate(
                load_json(self._paths.ground_truth_paths)
            ),
        )
