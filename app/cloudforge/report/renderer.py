"""Assembles ``report.md`` from on-disk scenario artifacts.

Report works standalone: it re-loads the spec, graph, findings, and ground truth
(plus optional scanner/OPA results) from the output tree and joins the section
builders. This decouples reporting from the in-memory generate/validate state.
"""

from __future__ import annotations

from pathlib import Path

from app.cloudforge.generate.base import ScenarioBundle
from app.cloudforge.io.loaders import load_json, load_yaml, write_text
from app.cloudforge.io.paths import ScenarioPaths
from app.cloudforge.models.findings import ExpectedFindings, GroundTruthPaths
from app.cloudforge.models.graph import ScenarioGraph
from app.cloudforge.models.scenario import ScenarioSpec
from app.cloudforge.report import sections


class ReportRenderer:
    """Renders a Markdown report for one scenario directory."""

    def __init__(self, base_dir: Path | str) -> None:
        self._paths = ScenarioPaths.from_dir(base_dir)

    def render(self) -> str:
        spec = ScenarioSpec.model_validate(load_yaml(self._paths.scenario_yaml))
        bundle = self._load_bundle()
        checkov_ok = self._paths.checkov_results.exists()
        opa_ok = self._paths.opa_results.exists()
        blocks = [
            sections.build_title(spec),
            sections.build_banner(),
            sections.build_summary(spec),
            sections.build_resources(bundle),
            sections.build_findings(bundle),
            sections.build_critical_path(bundle),
            sections.build_scanner_summary(
                checkov_ok, "checkov results present in scanner_results/."
            ),
            sections.build_opa_summary(opa_ok, "OPA results present in opa_results.json."),
            sections.build_remediation(bundle),
            sections.build_limitations(),
        ]
        return "\n\n".join(blocks) + "\n"

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
