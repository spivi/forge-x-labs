"""Report renderer tests (check 5: report generated with required banner)."""

from __future__ import annotations

from pathlib import Path

from app.cloudforge import constants
from app.cloudforge.report.renderer import ReportRenderer


def test_report_generated_contains_banner(generated_scenario: Path) -> None:
    report = ReportRenderer(generated_scenario).render()

    assert constants.LOCAL_ONLY_BANNER in report


def test_report_lists_critical_path(generated_scenario: Path) -> None:
    report = ReportRenderer(generated_scenario).render()

    assert "path-critical-01" in report
    assert "role-runtime" in report


def test_report_to_file_writes_markdown(generated_scenario: Path) -> None:
    written = ReportRenderer(generated_scenario).render_to_file()

    assert written.exists()
    assert written.read_text(encoding="utf-8").startswith("# Scenario Report")


def test_report_lists_remediation_order(generated_scenario: Path) -> None:
    report = ReportRenderer(generated_scenario).render()

    assert "Remediation Order" in report
