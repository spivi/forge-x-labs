"""Scanner-score robustness over real-shaped checkov fixtures (#115).

Clause S12 — scanner scoring must be stable across malformed, partial, empty, and
unexpected scanner output: never crash, never hide a missed/unexpected finding.

Each fixture in ``tests/cloudforge/fixtures/checkov/`` is copied verbatim onto a
freshly generated scenario's ``checkov.json`` and run through both entry points a
real caller uses (``scanner_score.score_scenario`` and ``ReportRenderer.render``),
so a crash surfaces the same way it would in the CLI. One test per fixture, per
the ticket's acceptance criteria, plus a parametrized sweep asserting the
universal "never crashes" property over the whole fixture set at once.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from app.cloudforge.io.paths import ScenarioPaths
from app.cloudforge.report.renderer import ReportRenderer
from app.cloudforge.validate import scanner_score, scanner_score_diagnostics
from app.cloudforge.validate.scanner_score import ScannerScore

_FIXTURES_DIR = Path(__file__).parent / "fixtures" / "checkov"

# Every fixture file, by name (used both for the "never crashes" sweep and to
# build human-readable, per-fixture test ids).
_ALL_FIXTURES = sorted(p.name for p in _FIXTURES_DIR.glob("*.json"))


def _install_fixture(paths: ScenarioPaths, fixture_name: str) -> None:
    paths.checkov_results.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(_FIXTURES_DIR / fixture_name, paths.checkov_results)


def _score_and_render(
    generated_scenario: Path, fixture_name: str
) -> tuple[ScannerScore | None, str]:
    """Install one fixture, then exercise both scorer entry points.

    Returns ``(score_or_None, rendered_report)`` — a caller asserts on whichever
    (or both) matter for that fixture. Never raises (that IS the property under
    test): any exception here is a real S12 crash bug, not a test bug.
    """
    paths = ScenarioPaths.from_dir(generated_scenario)
    _install_fixture(paths, fixture_name)
    score = scanner_score.score_scenario(paths)
    report = ReportRenderer(generated_scenario).render()
    return score, report


# --- universal property: NEVER crash, over every fixture at once -----------------


@pytest.mark.parametrize("fixture_name", _ALL_FIXTURES)
def test_scorer_never_crashes_on_any_fixture(generated_scenario: Path, fixture_name: str) -> None:
    """The core S12 guarantee, swept over the whole corpus in one parametrization."""
    _score_and_render(generated_scenario, fixture_name)  # must not raise


@pytest.mark.parametrize("fixture_name", _ALL_FIXTURES)
def test_report_always_has_scanner_score_section(
    generated_scenario: Path, fixture_name: str
) -> None:
    """A scanner-score section renders unconditionally — never dropped, never crashes."""
    _, report = _score_and_render(generated_scenario, fixture_name)
    assert "## Scanner Score" in report


# --- one targeted test per fixture (ticket requirement) --------------------------


def test_valid_with_expected_findings(generated_scenario: Path) -> None:
    score, _ = _score_and_render(generated_scenario, "valid_with_expected_findings.json")
    assert score is not None
    assert score.expected_findings == 5
    assert score.matched_findings == 4
    assert score.missed_findings == 1
    assert score.unexpected_findings == 0
    # Missed findings are never silently hidden: the count is exact and present.
    assert score.missed == score.missed_findings


def test_valid_with_none(generated_scenario: Path) -> None:
    score, _ = _score_and_render(generated_scenario, "valid_with_none.json")
    assert score is not None
    assert score.matched_findings == 0
    assert score.missed_findings == 5
    assert score.unexpected_findings == 0
    assert score.scanner_coverage_score == 0.0


def test_valid_with_unexpected(generated_scenario: Path) -> None:
    score, _ = _score_and_render(generated_scenario, "valid_with_unexpected.json")
    assert score is not None
    # Both failed checks resolve to no graph node -> both counted as unexpected,
    # never dropped just because they don't correspond to any expected finding.
    assert score.unexpected_findings == 2
    assert score.unexpected == 2
    assert score.matched_findings == 0
    assert score.missed_findings == 5


def test_partial_missing_results_key(generated_scenario: Path) -> None:
    """No ``results`` key at all — fail-soft to a well-formed, zero-signal score."""
    score, report = _score_and_render(generated_scenario, "partial_missing_results.json")
    assert score is not None
    assert score.matched_findings == 0
    assert score.missed_findings == score.expected_findings
    assert score.unexpected_findings == 0
    assert "## Scanner Score" in report


def test_partial_missing_check_id(generated_scenario: Path) -> None:
    """``check_id`` is not used for matching at all — a missing one still scores."""
    score, _ = _score_and_render(generated_scenario, "partial_missing_check_id.json")
    assert score is not None
    # resource=role_deploy still resolves and matches a real expected finding.
    assert score.matched_findings == 1
    assert score.missed_findings == 4


def test_partial_missing_resource_field(generated_scenario: Path) -> None:
    """An entry missing ``resource`` entirely is skipped, not counted, not hidden."""
    score, _ = _score_and_render(generated_scenario, "partial_missing_resource.json")
    assert score is not None
    # Only the sg_web entry (which HAS a resource) contributes; the check missing
    # `resource` is skipped and its skip is recorded in warnings, never silent.
    assert score.matched_findings == 1
    assert any("malformed" in w for w in score.warnings)


def test_unknown_check_ids(generated_scenario: Path) -> None:
    """check_id is never validated against a known-checks list — unknown ids score fine."""
    score, _ = _score_and_render(generated_scenario, "unknown_check_ids.json")
    assert score is not None
    assert score.matched_findings == 2
    assert score.missed_findings == 3


def test_duplicated_failed_checks(generated_scenario: Path) -> None:
    """Duplicates are deduped by resolved graph node — never double- or under-counted."""
    score, _ = _score_and_render(generated_scenario, "duplicated_failed_checks.json")
    assert score is not None
    # 3 duplicate checks on role_deploy -> 1 matched finding (passrole), deduped.
    assert score.matched_findings == 1
    # 2 duplicate checks on an unresolvable ghost resource -> 1 unexpected, deduped.
    assert score.unexpected_findings == 1


def test_multiple_frameworks(generated_scenario: Path) -> None:
    """``check_type`` (terraform/terraform_plan/kubernetes) is irrelevant to matching."""
    score, _ = _score_and_render(generated_scenario, "multiple_frameworks.json")
    assert score is not None
    assert score.matched_findings == 3
    assert score.missed_findings == 2


def test_invalid_json_truncated(generated_scenario: Path) -> None:
    score, report = _score_and_render(generated_scenario, "invalid_json_truncated.json")
    assert score is None
    reason = scanner_score_diagnostics.not_scored_reason(
        ScenarioPaths.from_dir(generated_scenario)
    )
    assert reason is not None
    assert "checkov.json" in reason
    assert "checkov.json" in report


def test_invalid_json_garbage(generated_scenario: Path) -> None:
    score, report = _score_and_render(generated_scenario, "invalid_json_garbage.json")
    assert score is None
    assert "## Scanner Score" in report


def test_empty_file(generated_scenario: Path) -> None:
    """A zero-byte checkov.json — a scanner crash before it wrote anything."""
    score, report = _score_and_render(generated_scenario, "empty_file.json")
    assert score is None
    reason = scanner_score_diagnostics.not_scored_reason(
        ScenarioPaths.from_dir(generated_scenario)
    )
    assert reason is not None
    assert "checkov.json" in report


def test_huge_file(generated_scenario: Path) -> None:
    """5,000 failed checks: no crash, no timeout, missed/unexpected still exact."""
    score, _ = _score_and_render(generated_scenario, "huge_file.json")
    assert score is not None
    # 1667 checks land on the 5 known resources (round-robin every 3rd entry);
    # the rest are unresolvable ghost resources -> counted unexpected, never hidden.
    assert score.matched_findings + score.missed_findings == score.expected_findings
    assert score.unexpected_findings > 0


def test_wrong_schema_top_level_array(generated_scenario: Path) -> None:
    """A bare JSON array where an object is expected — fail-soft, not a crash."""
    score, report = _score_and_render(generated_scenario, "wrong_schema_top_level_array.json")
    assert score is None
    assert "## Scanner Score" in report


def test_wrong_schema_failed_checks_object(generated_scenario: Path) -> None:
    """``failed_checks`` is an object instead of a list — fail-soft, not a crash."""
    score, report = _score_and_render(generated_scenario, "wrong_schema_failed_checks_object.json")
    assert score is None
    reason = scanner_score_diagnostics.not_scored_reason(
        ScenarioPaths.from_dir(generated_scenario)
    )
    assert reason is not None
    assert "expected a list" in reason
    assert "## Scanner Score" in report


# --- fixture-count sanity: keep this in lockstep with the ticket's required list -


def test_fixture_set_covers_every_required_category() -> None:
    """Guards against silently dropping a fixture file (accidental deletion)."""
    names = set(_ALL_FIXTURES)
    required_substrings = [
        "valid_with_expected_findings",
        "valid_with_none",
        "valid_with_unexpected",
        "partial_missing_results",
        "partial_missing_check_id",
        "partial_missing_resource",
        "unknown_check_ids",
        "duplicated_failed_checks",
        "multiple_frameworks",
        "invalid_json_truncated",
        "invalid_json_garbage",
        "empty_file",
        "huge_file",
        "wrong_schema_top_level_array",
        "wrong_schema_failed_checks_object",
    ]
    for required in required_substrings:
        assert any(required in name for name in names), f"missing fixture: {required}"
    assert len(names) == len(required_substrings)
