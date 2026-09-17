"""``export.py`` tests: the training-export gate + writer (design §9.6).

Hand-built truth-table tests exercise ``is_exportable``/``export_training`` in
isolation (each design §9.6 exclusion reason, ``--include-restricted``, the
``mappings_only`` admission); a real end-to-end test loads the actual 14-seed catalog
through the real registry -> adapter -> normalizer -> validator -> scorer pipeline and
asserts the HONEST exported count (12/14 — the two absence-of-logging seeds are below
the 0.70 quality bar per ``test_seed_fragments.py``'s
``TestHonestExportability``). Round-trip tests prove the written JSONL reloads to
identical ``RiskPattern``s.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.cloudforge.learn.adapters.rule_catalog_yaml import RuleCatalogYamlAdapter
from app.cloudforge.learn.corpus import load_corpus
from app.cloudforge.learn.export import (
    CORPUS_FILENAME,
    MANIFEST_FILENAME,
    export_training,
    is_exportable,
    write_training_export,
)
from app.cloudforge.learn.export_models import EXPORT_RULESET, TrainingExportManifest
from app.cloudforge.learn.normalizer import PatternNormalizer
from app.cloudforge.learn.pattern_enums import SafetyClassification, ValidationStatus
from app.cloudforge.learn.pattern_models import RiskPattern
from app.cloudforge.learn.quality import EXPORT_QUALITY_BAR, score_pattern
from app.cloudforge.learn.registry import get_entry, load_registry
from app.cloudforge.learn.source_models import ReuseStatus
from app.cloudforge.learn.validate import validate_fragment

from .conftest import build_pattern

_REGISTRY = Path("data/source_registry.yaml")
_SOURCE_ID = "local-rule-catalog"
_SEED_COUNT = 14
_EXPECTED_EXPORTABLE = 12
_HONESTLY_SIMPLE_SEED_IDS = {
    "local-rule-catalog-s3-missing-access-logging-aws-001",
    "local-rule-catalog-cloudtrail-logging-missing-aws-008",
}


def _eligible_pattern(
    *,
    validation_status: ValidationStatus = ValidationStatus.VALID,
    safety_classification: SafetyClassification = SafetyClassification.DEFENSIVE_PATTERN,
    reuse_status: ReuseStatus = ReuseStatus.FULL_REUSE,
    allowed_for_training: bool = True,
    **overrides: object,
) -> RiskPattern:
    """A hand-built pattern that clears the export gate by default."""
    pattern = build_pattern(
        reuse_status=reuse_status,
        allowed_for_training=allowed_for_training,
        validation_status=validation_status,
        safety_classification=safety_classification,
    )
    if overrides:
        pattern = pattern.model_copy(update=overrides)
    return pattern


# --- is_exportable: the design §9.6 gate, condition by condition ---------------------


class TestIsExportableGate:
    def test_eligible_high_quality_pattern_is_exported(self) -> None:
        pattern = _eligible_pattern(quality_score=0.85)
        assert pattern.training_eligible is True

        ok, reason = is_exportable(pattern)

        assert ok is True
        assert reason == ""

    def test_below_quality_bar_pattern_is_excluded(self) -> None:
        pattern = _eligible_pattern(quality_score=0.50)

        ok, reason = is_exportable(pattern)

        assert ok is False
        assert reason == "below_quality_bar"

    def test_quality_score_exactly_at_bar_is_exported(self) -> None:
        pattern = _eligible_pattern(quality_score=EXPORT_QUALITY_BAR)

        ok, _reason = is_exportable(pattern)

        assert ok is True

    def test_restricted_reuse_status_is_excluded_by_default(self) -> None:
        pattern = _eligible_pattern(
            reuse_status=ReuseStatus.RESTRICTED,
            allowed_for_training=True,
            quality_score=0.90,
        )
        assert pattern.training_eligible is False

        ok, reason = is_exportable(pattern)

        assert ok is False
        assert reason == "restricted_source_excluded"

    def test_metadata_only_reuse_status_is_excluded(self) -> None:
        pattern = _eligible_pattern(
            reuse_status=ReuseStatus.METADATA_ONLY,
            allowed_for_training=False,
            quality_score=0.90,
        )

        ok, reason = is_exportable(pattern)

        assert ok is False
        assert reason == "not_training_eligible"

    def test_unknown_reuse_status_is_excluded(self) -> None:
        pattern = _eligible_pattern(
            reuse_status=ReuseStatus.UNKNOWN,
            allowed_for_training=False,
            quality_score=0.90,
        )

        ok, reason = is_exportable(pattern)

        assert ok is False
        assert reason == "not_training_eligible"

    def test_mappings_only_reuse_status_is_exported_fxl_d007(self) -> None:
        # CSA CCM control-ID mappings ARE training-eligible.
        pattern = _eligible_pattern(
            reuse_status=ReuseStatus.MAPPINGS_ONLY,
            allowed_for_training=True,
            quality_score=0.90,
        )
        assert pattern.training_eligible is True

        ok, reason = is_exportable(pattern)

        assert ok is True
        assert reason == ""

    def test_invalid_validation_status_is_excluded(self) -> None:
        pattern = _eligible_pattern(validation_status=ValidationStatus.INVALID, quality_score=0.90)

        ok, reason = is_exportable(pattern)

        assert ok is False
        assert reason == "not_training_eligible"

    def test_allowed_for_training_false_is_excluded_even_with_full_reuse(self) -> None:
        pattern = _eligible_pattern(
            reuse_status=ReuseStatus.FULL_REUSE,
            allowed_for_training=False,
            quality_score=0.90,
        )

        ok, reason = is_exportable(pattern)

        assert ok is False
        assert reason == "not_training_eligible"

    def test_unsafe_operational_is_never_exported(self) -> None:
        pattern = _eligible_pattern(
            safety_classification=SafetyClassification.UNSAFE_OPERATIONAL,
            quality_score=0.99,
        )

        ok, reason = is_exportable(pattern)

        assert ok is False
        assert reason == "unsafe_operational"

    def test_restricted_source_classification_without_reuse_flag_is_excluded(self) -> None:
        pattern = _eligible_pattern(
            safety_classification=SafetyClassification.RESTRICTED_SOURCE,
            quality_score=0.90,
        )

        ok, reason = is_exportable(pattern)

        assert ok is False
        assert reason == "not_training_eligible"


# --- --include-restricted -------------------------------------------------------------


class TestIncludeRestricted:
    def test_restricted_but_otherwise_eligible_is_admitted_only_with_flag(self) -> None:
        pattern = _eligible_pattern(
            reuse_status=ReuseStatus.RESTRICTED,
            allowed_for_training=True,
            quality_score=0.90,
        )

        without_flag, reason_without = is_exportable(pattern, include_restricted=False)
        with_flag, reason_with = is_exportable(pattern, include_restricted=True)

        assert without_flag is False
        assert reason_without == "restricted_source_excluded"
        assert with_flag is True
        assert reason_with == ""

    def test_include_restricted_still_honors_the_quality_bar(self) -> None:
        pattern = _eligible_pattern(
            reuse_status=ReuseStatus.RESTRICTED,
            allowed_for_training=True,
            quality_score=0.10,
        )

        ok, reason = is_exportable(pattern, include_restricted=True)

        assert ok is False
        assert reason == "below_quality_bar"

    def test_include_restricted_never_admits_unsafe_operational(self) -> None:
        pattern = _eligible_pattern(
            reuse_status=ReuseStatus.RESTRICTED,
            allowed_for_training=True,
            safety_classification=SafetyClassification.UNSAFE_OPERATIONAL,
            quality_score=0.99,
        )

        ok, reason = is_exportable(pattern, include_restricted=True)

        assert ok is False
        assert reason == "unsafe_operational"

    def test_include_restricted_does_not_admit_metadata_only(self) -> None:
        # Only reuse_status == restricted is relaxed; metadata_only stays excluded.
        pattern = _eligible_pattern(
            reuse_status=ReuseStatus.METADATA_ONLY,
            allowed_for_training=False,
            quality_score=0.90,
        )

        ok, reason = is_exportable(pattern, include_restricted=True)

        assert ok is False
        assert reason == "not_training_eligible"


# --- export_training: manifest + records ----------------------------------------------


class TestExportTraining:
    def test_manifest_records_include_restricted_flag_and_affected_count(self) -> None:
        restricted = _eligible_pattern(
            id="restricted-1",
            reuse_status=ReuseStatus.RESTRICTED,
            allowed_for_training=True,
            quality_score=0.90,
        )
        eligible = _eligible_pattern(id="eligible-1", quality_score=0.90)

        result = export_training([restricted, eligible], include_restricted=True)

        assert result.manifest.include_restricted is True
        assert result.manifest.restricted_admitted_count == 1
        assert result.manifest.exported_count == 2
        assert {p.id for p in result.records} == {"restricted-1", "eligible-1"}

    def test_manifest_without_include_restricted_reports_zero_admitted(self) -> None:
        restricted = _eligible_pattern(
            id="restricted-2",
            reuse_status=ReuseStatus.RESTRICTED,
            allowed_for_training=True,
            quality_score=0.90,
        )

        result = export_training([restricted], include_restricted=False)

        assert result.manifest.include_restricted is False
        assert result.manifest.restricted_admitted_count == 0
        assert result.manifest.exported_count == 0
        assert result.manifest.excluded_breakdown.restricted_source_excluded == 1

    def test_manifest_ruleset_matches_design_ruleset(self) -> None:
        result = export_training([_eligible_pattern(quality_score=0.90)])

        assert result.manifest.ruleset == list(EXPORT_RULESET)
        assert result.manifest.quality_bar == EXPORT_QUALITY_BAR

    def test_manifest_counts_total_input_and_excluded(self) -> None:
        eligible = _eligible_pattern(id="ok-1", quality_score=0.90)
        below_bar = _eligible_pattern(id="low-1", quality_score=0.10)
        unsafe = _eligible_pattern(
            id="unsafe-1",
            safety_classification=SafetyClassification.UNSAFE_OPERATIONAL,
            quality_score=0.90,
        )

        result = export_training([eligible, below_bar, unsafe])

        assert result.manifest.total_input == 3
        assert result.manifest.exported_count == 1
        assert result.manifest.excluded_count == 2
        assert result.manifest.excluded_breakdown.below_quality_bar == 1
        assert result.manifest.excluded_breakdown.unsafe_operational == 1

    def test_manifest_coverage_reflects_admitted_records_only(self) -> None:
        eligible = _eligible_pattern(id="ok-2", quality_score=0.90)
        below_bar = _eligible_pattern(id="low-2", quality_score=0.10)

        result = export_training([eligible, below_bar])

        assert sum(result.manifest.provider_coverage.values()) == 1
        assert sum(result.manifest.weakness_family_coverage.values()) == 1

    def test_export_training_is_pure_no_files_written(self, tmp_path: Path) -> None:
        export_training([_eligible_pattern(quality_score=0.90)])

        assert list(tmp_path.iterdir()) == []


# --- write_training_export: JSONL + manifest on disk -----------------------------------


class TestWriteTrainingExport:
    def test_writes_corpus_jsonl_and_manifest_json(self, tmp_path: Path) -> None:
        result = export_training([_eligible_pattern(quality_score=0.90)])

        write_training_export(result, tmp_path)

        assert (tmp_path / CORPUS_FILENAME).exists()
        assert (tmp_path / MANIFEST_FILENAME).exists()

    def test_manifest_json_is_valid_and_matches_model(self, tmp_path: Path) -> None:
        result = export_training([_eligible_pattern(quality_score=0.90)])

        write_training_export(result, tmp_path)

        payload = json.loads((tmp_path / MANIFEST_FILENAME).read_text(encoding="utf-8"))
        reloaded = TrainingExportManifest.model_validate(payload)
        assert reloaded == result.manifest

    def test_jsonl_round_trips_to_equal_risk_patterns(self, tmp_path: Path) -> None:
        result = export_training([_eligible_pattern(id="rt-1", quality_score=0.90)])

        write_training_export(result, tmp_path)
        reloaded = load_corpus(tmp_path / CORPUS_FILENAME)

        assert reloaded == result.records

    def test_writing_twice_is_byte_identical(self, tmp_path: Path) -> None:
        result = export_training([_eligible_pattern(id="rt-2", quality_score=0.90)])

        write_training_export(result, tmp_path)
        first_corpus = (tmp_path / CORPUS_FILENAME).read_text(encoding="utf-8")
        first_manifest = (tmp_path / MANIFEST_FILENAME).read_text(encoding="utf-8")

        write_training_export(result, tmp_path)
        second_corpus = (tmp_path / CORPUS_FILENAME).read_text(encoding="utf-8")
        second_manifest = (tmp_path / MANIFEST_FILENAME).read_text(encoding="utf-8")

        assert first_corpus == second_corpus
        assert first_manifest == second_manifest

    def test_creates_output_dir_if_missing(self, tmp_path: Path) -> None:
        out_dir = tmp_path / "nested" / "training_export"
        result = export_training([_eligible_pattern(quality_score=0.90)])

        write_training_export(result, out_dir)

        assert (out_dir / CORPUS_FILENAME).exists()


# --- real 14-seed catalog integration test ---------------------------------------------


def _load_scored_seed_patterns() -> list[RiskPattern]:
    registry = load_registry(_REGISTRY)
    entry = get_entry(registry, _SOURCE_ID)
    assert entry.path is not None
    records = RuleCatalogYamlAdapter().extract(entry, Path(entry.path))
    normalizer = PatternNormalizer()
    patterns = [normalizer.normalize(r) for r in records]
    validated = [validate_fragment(p) for p in patterns]
    return [score_pattern(p)[0] for p in validated]


class TestRealSeedCatalogExport:
    def test_real_corpus_exports_the_honest_twelve_of_fourteen(self) -> None:
        patterns = _load_scored_seed_patterns()
        assert len(patterns) == _SEED_COUNT

        result = export_training(patterns)

        assert result.manifest.total_input == _SEED_COUNT
        assert result.manifest.exported_count == _EXPECTED_EXPORTABLE
        assert result.manifest.excluded_count == _SEED_COUNT - _EXPECTED_EXPORTABLE

    def test_real_corpus_excludes_exactly_the_two_absence_of_logging_seeds(self) -> None:
        patterns = _load_scored_seed_patterns()

        result = export_training(patterns)

        exported_ids = {p.id for p in result.records}
        assert _HONESTLY_SIMPLE_SEED_IDS.isdisjoint(exported_ids)
        assert len(_HONESTLY_SIMPLE_SEED_IDS) == _SEED_COUNT - _EXPECTED_EXPORTABLE

    def test_real_corpus_excluded_reason_is_below_quality_bar_not_ineligibility(self) -> None:
        patterns = _load_scored_seed_patterns()

        result = export_training(patterns)

        # The two excluded seeds are training_eligible (#98 seeds are all
        # full_reuse/valid) — they are excluded ONLY for quality, never eligibility.
        assert result.manifest.excluded_breakdown.below_quality_bar == 2
        assert result.manifest.excluded_breakdown.not_training_eligible == 0
        assert result.manifest.excluded_breakdown.unsafe_operational == 0
        assert result.manifest.excluded_breakdown.restricted_source_excluded == 0

    def test_real_corpus_manifest_coverage_matches_exported_records(self) -> None:
        patterns = _load_scored_seed_patterns()

        result = export_training(patterns)

        assert sum(result.manifest.provider_coverage.values()) == _EXPECTED_EXPORTABLE
        assert sum(result.manifest.weakness_family_coverage.values()) == _EXPECTED_EXPORTABLE
        assert set(result.manifest.provider_coverage.keys()) <= {"aws", "azure", "gcp"}

    def test_real_corpus_round_trips_through_write_training_export(self, tmp_path: Path) -> None:
        patterns = _load_scored_seed_patterns()

        result = export_training(patterns)
        write_training_export(result, tmp_path)
        reloaded = load_corpus(tmp_path / CORPUS_FILENAME)

        assert len(reloaded) == _EXPECTED_EXPORTABLE
        assert {p.id for p in reloaded} == {p.id for p in result.records}
