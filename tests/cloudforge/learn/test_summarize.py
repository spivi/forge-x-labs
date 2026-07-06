"""``summarize.py`` tests (FXL-73): pure formatting of a ``CorpusSummary``."""

from __future__ import annotations

from app.cloudforge.learn.quality import CorpusSummary
from app.cloudforge.learn.summarize import render_summary_lines


def _empty_summary() -> CorpusSummary:
    return CorpusSummary(
        total=0,
        valid=0,
        exportable=0,
        restricted=0,
        unsafe=0,
        rejected=0,
        duplicates=0,
        average_quality=0.0,
        top_rejection_reasons=[],
        provider_coverage={},
        domain_coverage={},
        weakness_family_coverage={},
    )


def _populated_summary() -> CorpusSummary:
    return CorpusSummary(
        total=2,
        valid=2,
        exportable=1,
        restricted=0,
        unsafe=0,
        rejected=1,
        duplicates=0,
        average_quality=0.72,
        top_rejection_reasons=["no expected_findings reference the fragment"],
        provider_coverage={"aws": 2},
        domain_coverage={"storage": 1, "iam": 1},
        weakness_family_coverage={"s3_public_exposure": 1, "iam_excessive_privilege": 1},
    )


class TestRenderSummaryLinesEmptyCorpus:
    def test_shows_zero_counts(self) -> None:
        lines = render_summary_lines(_empty_summary())

        assert "total patterns: 0" in lines

    def test_shows_none_for_every_empty_coverage_bucket(self) -> None:
        lines = render_summary_lines(_empty_summary())

        assert lines.count("  (none)") == 3

    def test_omits_top_rejection_reasons_section_when_empty(self) -> None:
        lines = render_summary_lines(_empty_summary())

        assert "top rejection reasons:" not in lines


class TestRenderSummaryLinesPopulatedCorpus:
    def test_shows_counts_and_coverage_rows(self) -> None:
        lines = render_summary_lines(_populated_summary())

        assert "total patterns: 2" in lines
        assert "  aws: 2" in lines
        assert "  storage: 1" in lines
        assert "  s3_public_exposure: 1" in lines

    def test_shows_average_quality_and_top_rejection_reasons(self) -> None:
        lines = render_summary_lines(_populated_summary())

        assert "average quality_score: 0.72" in lines
        assert "top rejection reasons:" in lines
        assert "  - no expected_findings reference the fragment" in lines
