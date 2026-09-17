"""``dedup()`` tests: deterministic corpus dedup (design §9.3).

Builds ``RiskPattern``s via the shared ``build_pattern`` helper (conftest) and
``model_copy`` to vary the dedup-key fields, mirroring how the normalizer's real
output would collide or diverge. No fuzzy matching, no embeddings — exact key
equality only.
"""

from __future__ import annotations

import random

from app.cloudforge.learn.dedup import DedupReport, dedup
from app.cloudforge.learn.pattern_models import RiskPattern

from .conftest import build_pattern


def _pattern(pattern_id: str, *, quality_score: float = 0.0, **overrides: object) -> RiskPattern:
    """A pattern with a distinct id/quality_score, sharing the base key by default."""
    base = build_pattern()
    return base.model_copy(update={"id": pattern_id, "quality_score": quality_score, **overrides})


# --- basic grouping --------------------------------------------------------------


def test_two_patterns_with_same_key_are_deduped_to_one_survivor() -> None:
    a = _pattern("pattern-a", quality_score=0.5)
    b = _pattern("pattern-b", quality_score=0.5)

    survivors, report = dedup([a, b])

    assert len(survivors) == 1
    assert isinstance(report, DedupReport)


def test_two_patterns_with_different_keys_are_both_kept() -> None:
    a = _pattern("pattern-a", affected_resource_types=["aws_s3_bucket"])
    b = _pattern("pattern-b", affected_resource_types=["aws_iam_role"])

    survivors, report = dedup([a, b])

    assert {p.id for p in survivors} == {"pattern-a", "pattern-b"}
    assert report.dropped_duplicate_ids == {}


def test_key_ignores_field_order_via_sorting() -> None:
    a = _pattern("pattern-a", affected_resource_types=["aws_s3_bucket", "aws_iam_role"])
    b = _pattern("pattern-b", affected_resource_types=["aws_iam_role", "aws_s3_bucket"])

    survivors, _report = dedup([a, b])

    assert len(survivors) == 1


# --- quality-score survivor selection --------------------------------------------


def test_higher_quality_score_survives() -> None:
    low = _pattern("low-quality", quality_score=0.2)
    high = _pattern("high-quality", quality_score=0.9)

    survivors, report = dedup([low, high])

    assert len(survivors) == 1
    assert survivors[0].id == "high-quality"
    assert report.dropped_duplicate_ids == {"high-quality": ["low-quality"]}


def test_identical_except_quality_score_higher_survives_lower_recorded_as_duplicate() -> None:
    lower = _pattern("id-lower", quality_score=0.1)
    higher = _pattern("id-higher", quality_score=0.99)

    survivors, report = dedup([lower, higher])

    assert survivors[0].id == "id-higher"
    assert "id-lower" in report.dropped_duplicate_ids["id-higher"]


def test_tie_on_quality_score_breaks_deterministically_by_id() -> None:
    # Same quality_score (e.g. both default 0.0 pre-quality-ticket #69) -> id tie-break.
    a = _pattern("aaa-first", quality_score=0.0)
    b = _pattern("zzz-second", quality_score=0.0)

    survivors, report = dedup([a, b])

    # max() picks the lexicographically largest id on a tie (deterministic, documented).
    assert survivors[0].id == "zzz-second"
    assert report.dropped_duplicate_ids == {"zzz-second": ["aaa-first"]}


# --- provenance / duplicate-id recording -----------------------------------------


def test_dropped_duplicate_source_mappings_are_merged_into_survivor() -> None:
    low = _pattern("low", quality_score=0.1, source_mappings=["CKV_AWS_1"])
    high = _pattern("high", quality_score=0.9, source_mappings=["CKV_AWS_2"])

    survivors, _report = dedup([low, high])

    assert survivors[0].source_mappings == ["CKV_AWS_1", "CKV_AWS_2"]


def test_three_way_collision_merges_all_dropped_mappings_and_ids() -> None:
    a = _pattern("a", quality_score=0.1, source_mappings=["M1"])
    b = _pattern("b", quality_score=0.9, source_mappings=["M2"])
    c = _pattern("c", quality_score=0.3, source_mappings=["M3"])

    survivors, report = dedup([a, b, c])

    assert len(survivors) == 1
    assert survivors[0].id == "b"
    assert survivors[0].source_mappings == ["M1", "M2", "M3"]
    assert report.dropped_duplicate_ids["b"] == ["a", "c"]


def test_report_groups_key_maps_to_survivor_and_dropped_ids() -> None:
    low = _pattern("low", quality_score=0.1)
    high = _pattern("high", quality_score=0.9)

    _survivors, report = dedup([low, high])

    (group,) = report.groups.values()
    assert group == ["high", "low"]


# --- determinism (shuffle test) ---------------------------------------------------


def test_dedup_is_deterministic_regardless_of_input_order() -> None:
    patterns = [
        _pattern("dup-low", quality_score=0.2),
        _pattern("dup-high", quality_score=0.9),
        _pattern("distinct-1", affected_resource_types=["aws_lambda_function"]),
        _pattern("distinct-2", affected_resource_types=["aws_kms_key"]),
        _pattern("dup-mid", quality_score=0.5),
    ]

    baseline_survivors, baseline_report = dedup(patterns)

    shuffled = list(patterns)
    rng = random.Random(1234)
    for _ in range(5):
        rng.shuffle(shuffled)
        survivors, report = dedup(shuffled)

        assert [p.id for p in survivors] == [p.id for p in baseline_survivors]
        assert report == baseline_report


def test_dedup_empty_list_returns_no_survivors() -> None:
    survivors, report = dedup([])

    assert survivors == []
    assert report.survivor_ids == []
    assert report.dropped_duplicate_ids == {}
    assert report.groups == {}


def test_dedup_single_pattern_is_its_own_survivor() -> None:
    only = _pattern("solo", quality_score=0.5)

    survivors, report = dedup([only])

    assert survivors == [only]
    assert report.dropped_duplicate_ids == {}
