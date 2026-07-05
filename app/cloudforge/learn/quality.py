"""Deterministic quality + realism scoring (design §9.4).

Rubric-based (NOT learned, no ML, no embeddings). ``score_pattern`` weights five
dimensions into ``quality_score`` — provenance completeness, fragment richness,
findings coverage, control mapping, and carried-through adapter confidence — plus a
share of the pattern's own ``realism_score`` (plausible resource-type + relationship
+ severity combination; incoherent combos are penalized). Every dimension helper is
pure and depends only on the pattern's own fields, so the same pattern always yields
the same scores (see ``test_scoring_is_deterministic_same_pattern_same_scores``).

``score_pattern`` returns ``(RiskPattern, PatternQualityReport)`` — the scored pattern
copy plus its rejection reasons / warnings / exportable flag — mirroring the
``dedup() -> (survivors, DedupReport)`` convention in ``dedup.py``, since those fields
are not (and must not become, per this ticket's scope) fields on ``RiskPattern``
itself. ``exportable`` is a convenience signal only (``quality_score >= 0.70`` and no
hard rejection) — the real export gate lives in ticket #71 (``export.py``, design §9.6).

``summarize_corpus`` aggregates a scored corpus into a ``CorpusSummary``: counts by
disposition (valid/exportable/restricted/unsafe/rejected), the average quality score,
the most common rejection reasons, and provider/domain/weakness-family coverage.
"""

from __future__ import annotations

from collections import Counter

from pydantic import BaseModel, ConfigDict

from app.cloudforge.learn.pattern_enums import SafetyClassification, ValidationStatus
from app.cloudforge.learn.pattern_models import RiskPattern
from app.cloudforge.learn.quality_dimensions import (
    control_mapping_score,
    findings_coverage_score,
    fragment_richness_score,
    provenance_completeness_score,
    realism_score,
)

EXPORT_QUALITY_BAR = 0.70

# quality_score dimension weights (design §9.4); confidence is the adapter's own,
# realism folds the pattern's realism_score in at a lower weight (it is also exposed
# standalone as `realism_score`). Weights sum to 1.0.
_WEIGHTS: dict[str, float] = {
    "provenance": 0.20,
    "fragment": 0.20,
    "findings": 0.20,
    "controls": 0.15,
    "confidence": 0.15,
    "realism": 0.10,
}

_HARD_REJECT_CLASSIFICATIONS: frozenset[SafetyClassification] = frozenset(
    {SafetyClassification.UNSAFE_OPERATIONAL}
)


class PatternQualityReport(BaseModel):
    """Per-pattern scoring outcome: rejection reasons, warnings, exportability."""

    model_config = ConfigDict(extra="forbid")

    pattern_id: str
    rejection_reasons: list[str]
    warnings: list[str]
    exportable: bool


class CorpusSummary(BaseModel):
    """Corpus-level quality summary (design §9.4/§9.5): coverage + averages."""

    model_config = ConfigDict(extra="forbid")

    total: int
    valid: int
    exportable: int
    restricted: int
    unsafe: int
    rejected: int
    duplicates: int
    average_quality: float
    top_rejection_reasons: list[str]
    provider_coverage: dict[str, int]
    domain_coverage: dict[str, int]
    weakness_family_coverage: dict[str, int]


def score_pattern(pattern: RiskPattern) -> tuple[RiskPattern, PatternQualityReport]:
    """Deterministically score ``pattern`` (design §9.4).

    Returns ``(scored_pattern, report)``: ``scored_pattern`` is a copy of ``pattern``
    with ``quality_score``/``realism_score`` set; ``report`` carries the rejection
    reasons, warnings, and the ``exportable`` convenience flag. Never mutates
    ``pattern``. Pure function of ``pattern``'s own fields — same input always
    yields the same output.
    """
    realism = realism_score(pattern)
    dimensions = {
        "provenance": provenance_completeness_score(pattern),
        "fragment": fragment_richness_score(pattern),
        "findings": findings_coverage_score(pattern),
        "controls": control_mapping_score(pattern),
        "confidence": pattern.confidence,
        "realism": realism,
    }
    quality = sum(_WEIGHTS[name] * value for name, value in dimensions.items())

    scored = pattern.model_copy(update={"quality_score": quality, "realism_score": realism})
    report = _build_report(scored)
    return scored, report


def _build_report(scored: RiskPattern) -> PatternQualityReport:
    reasons = _rejection_reasons(scored)
    warnings = _warnings(scored)
    exportable = not reasons and scored.quality_score >= EXPORT_QUALITY_BAR
    return PatternQualityReport(
        pattern_id=scored.id,
        rejection_reasons=reasons,
        warnings=warnings,
        exportable=exportable,
    )


def _rejection_reasons(pattern: RiskPattern) -> list[str]:
    reasons: list[str] = []
    if pattern.safety_classification in _HARD_REJECT_CLASSIFICATIONS:
        reasons.append(f"safety_classification is {pattern.safety_classification.value}")
    if pattern.validation_status is ValidationStatus.INVALID:
        reasons.append("graph_fragment failed validation")
    if not pattern.graph_fragment.nodes:
        reasons.append("graph_fragment has no nodes")
    if not pattern.expected_findings:
        reasons.append("no expected_findings reference the fragment")
    return reasons


def _warnings(pattern: RiskPattern) -> list[str]:
    warnings: list[str] = []
    if not pattern.graph_fragment.edges:
        warnings.append("graph_fragment has no edges")
    if not pattern.control_mappings and not pattern.missing_controls:
        warnings.append("no control_mappings or missing_controls")
    if pattern.confidence < 0.5:
        warnings.append(f"low adapter confidence ({pattern.confidence:.2f})")
    if pattern.quality_score < EXPORT_QUALITY_BAR:
        warnings.append(f"quality_score below export bar ({EXPORT_QUALITY_BAR})")
    return warnings


def summarize_corpus(patterns: list[RiskPattern], *, duplicates: int = 0) -> CorpusSummary:
    """Aggregate an already-scored ``patterns`` corpus into a ``CorpusSummary``.

    ``duplicates`` is an optional hint (e.g. from ``dedup.DedupReport``) surfaced
    verbatim on the summary; this module does not perform dedup itself.
    """
    if not patterns:
        return CorpusSummary(
            total=0,
            valid=0,
            exportable=0,
            restricted=0,
            unsafe=0,
            rejected=0,
            duplicates=duplicates,
            average_quality=0.0,
            top_rejection_reasons=[],
            provider_coverage={},
            domain_coverage={},
            weakness_family_coverage={},
        )

    reports = [_build_report(p) for p in patterns]
    reason_counts = Counter(reason for report in reports for reason in report.rejection_reasons)

    return CorpusSummary(
        total=len(patterns),
        valid=sum(1 for p in patterns if p.validation_status is ValidationStatus.VALID),
        exportable=sum(1 for report in reports if report.exportable),
        restricted=sum(
            1
            for p in patterns
            if p.safety_classification is SafetyClassification.RESTRICTED_SOURCE
        ),
        unsafe=sum(
            1
            for p in patterns
            if p.safety_classification is SafetyClassification.UNSAFE_OPERATIONAL
        ),
        rejected=sum(1 for report in reports if report.rejection_reasons),
        duplicates=duplicates,
        average_quality=sum(p.quality_score for p in patterns) / len(patterns),
        top_rejection_reasons=[reason for reason, _count in reason_counts.most_common(5)],
        provider_coverage=dict(Counter(p.cloud_provider.value for p in patterns)),
        domain_coverage=dict(Counter(domain.value for p in patterns for domain in p.domains)),
        weakness_family_coverage=dict(Counter(p.weakness_family.value for p in patterns)),
    )
