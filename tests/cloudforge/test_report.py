"""Report renderer tests (check 5: report generated with required banner)."""

from __future__ import annotations

import json
from pathlib import Path

from app.cloudforge import constants
from app.cloudforge.io.paths import ScenarioPaths
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


def test_report_scanner_score_not_scored_when_absent(generated_scenario: Path) -> None:
    report = ReportRenderer(generated_scenario).render()

    assert "## Scanner Score" in report
    assert "not scored: no scanner output." in report


def test_report_scanner_score_summary_when_present(generated_scenario: Path) -> None:
    paths = ScenarioPaths.from_dir(generated_scenario)
    payload = {
        "results": {
            "failed_checks": [
                {"check_id": "CKV_AWS_60", "resource": "aws_iam_role.role_deploy"},
                {"check_id": "CKV_AWS_23", "resource": "aws_security_group.sg_web"},
            ],
            "passed_checks": [],
        }
    }
    paths.checkov_results.parent.mkdir(parents=True, exist_ok=True)
    paths.checkov_results.write_text(json.dumps(payload), encoding="utf-8")

    report = ReportRenderer(generated_scenario).render()

    assert "## Scanner Score" in report
    assert "**Scanner:** checkov" in report
    assert "**Coverage score:**" in report
