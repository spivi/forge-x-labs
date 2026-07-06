"""Format a ``CorpusSummary`` for the ``cloudforge learn summarize`` command.

Pure formatting only — no scoring/aggregation logic (that lives in ``quality.py``).
Returns plain strings so the CLI stays a thin ``rich``-printing wrapper (design §10).
"""

from __future__ import annotations

from app.cloudforge.learn.quality import CorpusSummary


def render_summary_lines(summary: CorpusSummary) -> list[str]:
    """Render ``summary`` as human-readable lines (counts, coverage, quality)."""
    return [
        *_count_lines(summary),
        "",
        *_coverage_lines("provider", summary.provider_coverage),
        "",
        *_coverage_lines("domain", summary.domain_coverage),
        "",
        *_coverage_lines("weakness family", summary.weakness_family_coverage),
        "",
        *_quality_lines(summary),
    ]


def _count_lines(summary: CorpusSummary) -> list[str]:
    return [
        f"total patterns: {summary.total}",
        f"valid: {summary.valid}  exportable: {summary.exportable}  "
        f"restricted: {summary.restricted}  unsafe: {summary.unsafe}  "
        f"rejected: {summary.rejected}  duplicates: {summary.duplicates}",
    ]


def _coverage_lines(label: str, coverage: dict[str, int]) -> list[str]:
    header = [f"{label} coverage:"]
    if not coverage:
        return [*header, "  (none)"]
    rows = [f"  {name}: {count}" for name, count in sorted(coverage.items())]
    return [*header, *rows]


def _quality_lines(summary: CorpusSummary) -> list[str]:
    lines = [f"average quality_score: {summary.average_quality:.2f}"]
    if summary.top_rejection_reasons:
        lines.append("top rejection reasons:")
        lines.extend(f"  - {reason}" for reason in summary.top_rejection_reasons)
    return lines
