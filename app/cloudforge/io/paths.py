"""Single source of truth for every artifact path under a scenario directory.

Every command resolves paths through ``ScenarioPaths`` so the output-tree layout is
defined in exactly one place.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.cloudforge import constants


@dataclass(frozen=True)
class ScenarioPaths:
    """Resolved paths for one scenario output directory."""

    base: Path

    @classmethod
    def from_dir(cls, base: Path | str) -> ScenarioPaths:
        return cls(base=Path(base))

    @property
    def scenario_yaml(self) -> Path:
        return self.base / constants.SCENARIO_FILENAME

    @property
    def graph(self) -> Path:
        return self.base / constants.GRAPH_FILENAME

    @property
    def expected_findings(self) -> Path:
        return self.base / constants.EXPECTED_FINDINGS_FILENAME

    @property
    def ground_truth_paths(self) -> Path:
        return self.base / constants.GROUND_TRUTH_FILENAME

    @property
    def terraform_dir(self) -> Path:
        return self.base / constants.TERRAFORM_DIRNAME

    @property
    def scanner_results_dir(self) -> Path:
        return self.base / constants.SCANNER_RESULTS_DIRNAME

    @property
    def checkov_results(self) -> Path:
        return self.scanner_results_dir / constants.CHECKOV_RESULTS_FILENAME

    @property
    def opa_results(self) -> Path:
        return self.base / constants.OPA_RESULTS_FILENAME

    @property
    def scanner_score(self) -> Path:
        return self.base / constants.SCANNER_SCORE_FILENAME

    @property
    def report(self) -> Path:
        return self.base / constants.REPORT_FILENAME
