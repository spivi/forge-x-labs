"""``quality.py`` tests (FXL-69): deterministic rubric-based quality/realism scoring.

Builds ``RiskPattern``s via the shared ``build_pattern`` helper (conftest) plus
``model_copy`` to vary individual dimensions, and normalizes the real 14-entry seed
catalog (``data/rule_catalog/seed_patterns.yaml``) through the real adapter +
normalizer to score genuine corpus patterns end-to-end. No ML, no embeddings —
pure deterministic weighted dimensions.

``score_pattern`` returns ``(RiskPattern, PatternQualityReport)`` — mirroring the
``dedup() -> (survivors, DedupReport)`` convention already used in this package
(``dedup.py``) — since ``rejection_reasons``/``warnings``/``exportable`` are not
fields on ``RiskPattern`` itself (that model is out of scope to modify).
"""

from __future__ import annotations

from pathlib import Path

from app.cloudforge.learn.adapters.rule_catalog_yaml import RuleCatalogYamlAdapter
from app.cloudforge.learn.normalizer import PatternNormalizer
from app.cloudforge.learn.pattern_enums import Domain, SafetyClassification, ValidationStatus
from app.cloudforge.learn.pattern_models import RiskPattern
from app.cloudforge.learn.quality import (
    CorpusSummary,
    PatternQualityReport,
    score_pattern,
    summarize_corpus,
)
from app.cloudforge.learn.registry import get_entry, load_registry
from app.cloudforge.models.findings import ExpectedFinding, FindingFamily
from app.cloudforge.models.graph import ScenarioGraph

from .conftest import build_fragment, build_pattern

_REGISTRY_PATH = Path("data/source_registry.yaml")
_SOURCE_ID = "local-rule-catalog"


def _empty_fragment() -> ScenarioGraph:
    return ScenarioGraph(nodes=[], edges=[])


def _load_seed_patterns() -> list[RiskPattern]:
    registry = load_registry(_REGISTRY_PATH)
    entry = get_entry(registry, _SOURCE_ID)
    assert entry.path is not None
    records = RuleCatalogYamlAdapter().extract(entry, Path(entry.path))
    normalizer = PatternNormalizer()
    return [normalizer.normalize(r) for r in records]


def _scored_patterns(patterns: list[RiskPattern]) -> list[RiskPattern]:
    return [score_pattern(p)[0] for p in patterns]


# --- score_pattern: basic shape ---------------------------------------------------


def test_score_pattern_returns_a_risk_pattern_with_scores_set() -> None:
    pattern = build_pattern()

    scored, report = score_pattern(pattern)

    assert isinstance(scored, RiskPattern)
    assert isinstance(report, PatternQualityReport)
    assert 0.0 <= scored.quality_score <= 1.0
    assert 0.0 <= scored.realism_score <= 1.0


def test_score_pattern_does_not_mutate_its_input() -> None:
    pattern = build_pattern().model_copy(update={"quality_score": 0.0, "realism_score": 0.0})

    score_pattern(pattern)

    assert pattern.quality_score == 0.0
    assert pattern.realism_score == 0.0


def test_score_pattern_preserves_identity_fields() -> None:
    pattern = build_pattern()

    scored, _report = score_pattern(pattern)

    assert scored.id == pattern.id
    assert scored.title == pattern.title
    assert scored.graph_fragment == pattern.graph_fragment


def test_score_pattern_report_carries_rejection_reasons_and_warnings_and_exportable() -> None:
    _scored, report = score_pattern(build_pattern())

    assert isinstance(report.rejection_reasons, list)
    assert isinstance(report.warnings, list)
    assert isinstance(report.exportable, bool)
    assert report.pattern_id == build_pattern().id


# --- determinism -------------------------------------------------------------------


def test_scoring_is_deterministic_same_pattern_same_scores() -> None:
    pattern = build_pattern()

    first_pattern, first_report = score_pattern(pattern)
    second_pattern, second_report = score_pattern(pattern)

    assert first_pattern.quality_score == second_pattern.quality_score
    assert first_pattern.realism_score == second_pattern.realism_score
    assert first_report.rejection_reasons == second_report.rejection_reasons
    assert first_report.warnings == second_report.warnings
    assert first_report.exportable == second_report.exportable


def test_scoring_is_deterministic_across_many_repeats() -> None:
    pattern = build_pattern()
    scores = {score_pattern(pattern)[0].quality_score for _ in range(20)}

    assert len(scores) == 1


# --- rich vs sparse discrimination -------------------------------------------------


def test_rich_well_provenanced_pattern_scores_higher_than_sparse_pattern() -> None:
    rich = build_pattern()
    sparse = build_pattern().model_copy(
        update={
            "id": "sparse-001",
            "graph_fragment": _empty_fragment(),
            "expected_findings": [],
            "control_mappings": [],
            "missing_controls": [],
            "confidence": 0.1,
        }
    )

    rich_scored, _ = score_pattern(rich)
    sparse_scored, _ = score_pattern(sparse)

    assert rich_scored.quality_score > sparse_scored.quality_score


def test_pattern_missing_findings_and_fragment_scores_lower_than_baseline() -> None:
    baseline, _ = score_pattern(build_pattern())
    missing_both, _ = score_pattern(
        build_pattern().model_copy(
            update={
                "id": "missing-both",
                "graph_fragment": _empty_fragment(),
                "expected_findings": [],
            }
        )
    )

    assert missing_both.quality_score < baseline.quality_score


def test_fragment_richness_increases_with_more_structure() -> None:
    one_node = build_pattern().model_copy(
        update={
            "id": "one-node",
            "graph_fragment": ScenarioGraph(
                nodes=[build_fragment().nodes[0]],
                edges=[],
            ),
        }
    )
    two_node_one_edge = build_pattern().model_copy(update={"id": "two-node"})

    one_node_scored, _ = score_pattern(one_node)
    two_node_scored, _ = score_pattern(two_node_one_edge)

    assert two_node_scored.quality_score > one_node_scored.quality_score


# --- rejection reasons / warnings ---------------------------------------------------


def test_low_confidence_pattern_does_not_crash_and_stays_in_bounds() -> None:
    low_conf = build_pattern().model_copy(update={"confidence": 0.0})
    scored, _report = score_pattern(low_conf)
    assert scored.quality_score >= 0.0


def test_sparse_pattern_has_nonempty_rejection_reasons_or_warnings() -> None:
    sparse = build_pattern().model_copy(
        update={
            "id": "sparse-002",
            "graph_fragment": _empty_fragment(),
            "expected_findings": [],
            "control_mappings": [],
            "missing_controls": [],
            "confidence": 0.1,
        }
    )

    _scored, report = score_pattern(sparse)

    assert report.rejection_reasons or report.warnings


def test_exportable_is_false_when_quality_score_below_threshold() -> None:
    sparse = build_pattern().model_copy(
        update={
            "id": "sparse-003",
            "graph_fragment": _empty_fragment(),
            "expected_findings": [],
            "control_mappings": [],
            "missing_controls": [],
            "confidence": 0.0,
        }
    )

    scored, report = score_pattern(sparse)

    assert scored.quality_score < 0.70
    assert report.exportable is False


def test_exportable_false_on_hard_rejection_even_if_score_would_be_high() -> None:
    unsafe = build_pattern().model_copy(
        update={
            "id": "unsafe-001",
            "safety_classification": SafetyClassification.UNSAFE_OPERATIONAL,
        }
    )

    _scored, report = score_pattern(unsafe)

    assert report.exportable is False
    assert report.rejection_reasons


def test_exportable_true_for_rich_valid_pattern_above_threshold() -> None:
    scored, report = score_pattern(build_pattern())

    assert scored.quality_score >= 0.70
    assert report.exportable is True


# --- realism scoring: incoherent combo penalty --------------------------------------


def test_realism_penalizes_critical_severity_with_empty_fragment() -> None:
    coherent = build_pattern().model_copy(update={"id": "coherent", "severity": "critical"})
    incoherent = build_pattern().model_copy(
        update={
            "id": "incoherent",
            "severity": "critical",
            "graph_fragment": _empty_fragment(),
            "risky_relationships": [],
        }
    )

    coherent_scored, _ = score_pattern(coherent)
    incoherent_scored, _ = score_pattern(incoherent)

    assert incoherent_scored.realism_score < coherent_scored.realism_score


def test_realism_score_is_bounded() -> None:
    scored, _ = score_pattern(build_pattern())
    assert 0.0 <= scored.realism_score <= 1.0


def test_realism_rewards_plausible_relationship_for_severity() -> None:
    plausible = build_pattern().model_copy(
        update={"id": "plausible", "severity": "high", "risky_relationships": ["can_read"]}
    )
    implausible = build_pattern().model_copy(
        update={
            "id": "implausible",
            "severity": "low",
            "risky_relationships": ["can_read", "can_pass_role", "can_assume_role"],
            "affected_resource_types": [],
        }
    )

    plausible_scored, _ = score_pattern(plausible)
    implausible_scored, _ = score_pattern(implausible)

    assert plausible_scored.realism_score >= implausible_scored.realism_score


# --- individual dimensions ---------------------------------------------------------


def test_low_adapter_confidence_lowers_quality_score() -> None:
    high_conf = build_pattern().model_copy(update={"id": "hi-conf", "confidence": 0.95})
    low_conf = build_pattern().model_copy(update={"id": "lo-conf", "confidence": 0.05})

    high_scored, _ = score_pattern(high_conf)
    low_scored, _ = score_pattern(low_conf)

    assert high_scored.quality_score > low_scored.quality_score


def test_control_mapping_presence_increases_quality_score() -> None:
    with_controls = build_pattern().model_copy(update={"id": "with-controls"})
    without_controls = build_pattern().model_copy(
        update={"id": "no-controls", "control_mappings": [], "missing_controls": []}
    )

    with_scored, _ = score_pattern(with_controls)
    without_scored, _ = score_pattern(without_controls)

    assert with_scored.quality_score > without_scored.quality_score


def test_control_mapping_partial_presence_scores_between_both_and_neither() -> None:
    both = build_pattern().model_copy(update={"id": "both-controls"})
    only_missing = build_pattern().model_copy(
        update={"id": "only-missing-controls", "control_mappings": []}
    )
    neither = build_pattern().model_copy(
        update={"id": "neither-controls", "control_mappings": [], "missing_controls": []}
    )

    both_scored, _ = score_pattern(both)
    partial_scored, _ = score_pattern(only_missing)
    neither_scored, _ = score_pattern(neither)

    assert both_scored.quality_score > partial_scored.quality_score > neither_scored.quality_score


def test_invalid_validation_status_is_a_rejection_reason() -> None:
    invalid = build_pattern().model_copy(
        update={"id": "invalid-fragment", "validation_status": ValidationStatus.INVALID}
    )

    _scored, report = score_pattern(invalid)

    assert "graph_fragment failed validation" in report.rejection_reasons
    assert report.exportable is False


def test_findings_coverage_increases_quality_score() -> None:
    with_findings = build_pattern().model_copy(update={"id": "with-findings"})
    without_findings = build_pattern().model_copy(
        update={"id": "no-findings", "expected_findings": []}
    )

    with_scored, _ = score_pattern(with_findings)
    without_scored, _ = score_pattern(without_findings)

    assert with_scored.quality_score > without_scored.quality_score


# --- summarize_corpus ---------------------------------------------------------------


def test_summarize_corpus_on_empty_list() -> None:
    summary = summarize_corpus([])

    assert isinstance(summary, CorpusSummary)
    assert summary.total == 0
    assert summary.valid == 0
    assert summary.exportable == 0
    assert summary.average_quality == 0.0


def test_summarize_corpus_counts_total_and_exportable() -> None:
    rich, _ = score_pattern(build_pattern())
    sparse, _ = score_pattern(
        build_pattern().model_copy(
            update={
                "id": "sparse-004",
                "graph_fragment": _empty_fragment(),
                "expected_findings": [],
                "control_mappings": [],
                "missing_controls": [],
                "confidence": 0.0,
            }
        )
    )

    summary = summarize_corpus([rich, sparse])

    assert summary.total == 2
    assert summary.exportable == 1
    assert summary.rejected == 1


def test_summarize_corpus_counts_restricted_and_unsafe() -> None:
    restricted, _ = score_pattern(
        build_pattern().model_copy(
            update={
                "id": "restricted-001",
                "safety_classification": SafetyClassification.RESTRICTED_SOURCE,
            }
        )
    )
    unsafe, _ = score_pattern(
        build_pattern().model_copy(
            update={
                "id": "unsafe-002",
                "safety_classification": SafetyClassification.UNSAFE_OPERATIONAL,
            }
        )
    )
    valid, _ = score_pattern(build_pattern())

    summary = summarize_corpus([restricted, unsafe, valid])

    assert summary.restricted == 1
    assert summary.unsafe == 1
    assert summary.valid >= 1


def test_summarize_corpus_reports_provider_domain_family_coverage() -> None:
    patterns = _scored_patterns(_load_seed_patterns())

    summary = summarize_corpus(patterns)

    assert summary.total == 14
    assert set(summary.provider_coverage.keys()) == {"aws", "azure", "gcp"}
    assert summary.provider_coverage["aws"] >= 8
    assert summary.provider_coverage["azure"] >= 2
    assert summary.provider_coverage["gcp"] >= 3
    assert sum(summary.domain_coverage.values()) >= 14
    assert sum(summary.weakness_family_coverage.values()) == 14


def test_summarize_corpus_average_quality_is_within_bounds() -> None:
    patterns = _scored_patterns(_load_seed_patterns())

    summary = summarize_corpus(patterns)

    assert 0.0 <= summary.average_quality <= 1.0


def test_summarize_corpus_top_rejection_reasons_reflects_common_reasons() -> None:
    sparse_patterns = [
        score_pattern(
            build_pattern().model_copy(
                update={
                    "id": f"sparse-{i}",
                    "graph_fragment": _empty_fragment(),
                    "expected_findings": [],
                    "control_mappings": [],
                    "missing_controls": [],
                    "confidence": 0.0,
                }
            )
        )[0]
        for i in range(3)
    ]

    summary = summarize_corpus(sparse_patterns)

    assert summary.top_rejection_reasons
    assert summary.rejected == 3


def test_summarize_corpus_accepts_duplicate_count_hint() -> None:
    patterns = [score_pattern(build_pattern())[0]]

    summary = summarize_corpus(patterns, duplicates=2)

    assert summary.duplicates == 2


# --- real seed catalog end-to-end ---------------------------------------------------


def test_real_seed_catalog_scores_all_14_patterns_deterministically() -> None:
    patterns = _load_seed_patterns()
    assert len(patterns) == 14

    first_pass = [score_pattern(p)[0].quality_score for p in patterns]
    second_pass = [score_pattern(p)[0].quality_score for p in patterns]

    assert first_pass == second_pass
    assert all(0.0 <= q <= 1.0 for q in first_pass)


def test_real_seed_catalog_patterns_are_valid_ontology_after_scoring() -> None:
    patterns = _scored_patterns(_load_seed_patterns())

    for pattern in patterns:
        assert pattern.validation_status in {
            ValidationStatus.UNVALIDATED,
            ValidationStatus.VALID,
            ValidationStatus.INVALID,
        }
        assert pattern.domains
        for domain in pattern.domains:
            assert isinstance(domain, Domain)


def test_seed_with_added_finding_scores_higher_than_seed_without() -> None:
    patterns = _load_seed_patterns()
    # Since #98 the seeds DO carry hand-authored expected_findings, so the baseline is
    # made explicitly finding-less to isolate the findings-coverage dimension.
    base = patterns[0].model_copy(update={"expected_findings": []})
    enriched = base.model_copy(
        update={
            "expected_findings": [
                ExpectedFinding(
                    id="f-seed-1",
                    severity="high",
                    family=FindingFamily.S3_LOGGING_MISSING,
                    resource_ids=[base.graph_fragment.nodes[0].id],
                    expected_scanner_visibility="visible",
                    ground_truth="seed finding",
                    remediation="fix it",
                )
            ]
        }
    )

    base_scored, _ = score_pattern(base)
    enriched_scored, _ = score_pattern(enriched)

    assert enriched_scored.quality_score > base_scored.quality_score
