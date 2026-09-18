"""``corpus.py`` tests: JSONL load/save + corpus-level validation (§9.5).

Builds a real end-to-end corpus (14 seed rule-catalog entries -> normalize -> validate
-> dedup) as the "clean corpus" baseline, then crafts each design §9.5 violation
individually against hand-built ``RiskPattern``s (via the shared ``build_pattern``
helper) so every check is proven both on real data and in isolation. Reuses
``validate.validate_fragment`` for the fragment-validity check (never reinvented).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.cloudforge.errors import CloudforgeError
from app.cloudforge.learn.adapters.rule_catalog_yaml import RuleCatalogYamlAdapter
from app.cloudforge.learn.corpus import (
    CorpusLoadError,
    CorpusValidationReport,
    load_corpus,
    save_corpus,
    validate_corpus,
)
from app.cloudforge.learn.dedup import dedup
from app.cloudforge.learn.normalizer import PatternNormalizer
from app.cloudforge.learn.pattern_enums import SafetyClassification, ValidationStatus
from app.cloudforge.learn.pattern_models import RiskPattern
from app.cloudforge.learn.registry import get_entry, load_registry
from app.cloudforge.learn.source_models import ReuseStatus
from app.cloudforge.learn.validate import validate_fragment
from app.cloudforge.models.graph import GraphNode, NodeSecurity, NodeTags, NodeType, ScenarioGraph

from .conftest import build_fragment, build_pattern

_REGISTRY = Path("data/source_registry.yaml")
_SOURCE_ID = "local-rule-catalog"


# --- real end-to-end corpus: seeds -> normalize -> validate -> dedup ------------------


def _real_corpus() -> list[RiskPattern]:
    registry = load_registry(_REGISTRY)
    entry = get_entry(registry, _SOURCE_ID)
    assert entry.path is not None
    records = RuleCatalogYamlAdapter().extract(entry, Path(entry.path))
    normalizer = PatternNormalizer()
    validated = [validate_fragment(normalizer.normalize(r)) for r in records]
    survivors, _report = dedup(validated)
    return survivors


class TestRealCorpusEndToEnd:
    def test_fourteen_seeds_normalize_and_dedup_to_a_real_corpus(self) -> None:
        corpus = _real_corpus()
        assert len(corpus) >= 12
        assert all(p.validation_status is ValidationStatus.VALID for p in corpus)

    def test_clean_real_corpus_passes_validate_corpus(self) -> None:
        corpus = _real_corpus()
        report = validate_corpus(corpus)
        assert report.passed, report.issues
        assert report.pattern_count == len(corpus)

    def test_clean_real_corpus_round_trips_losslessly_through_jsonl(self, tmp_path: Path) -> None:
        corpus = _real_corpus()
        path = tmp_path / "corpus.jsonl"

        save_corpus(corpus, path)
        reloaded = load_corpus(path)

        assert [p.model_dump(mode="json") for p in reloaded] == [
            p.model_dump(mode="json") for p in corpus
        ]


# --- load / save: round trip + determinism + malformed input -------------------------


class TestLoadSaveRoundTrip:
    def test_round_trip_is_lossless(self, tmp_path: Path) -> None:
        patterns = [build_pattern()]
        path = tmp_path / "corpus.jsonl"

        save_corpus(patterns, path)
        reloaded = load_corpus(path)

        assert len(reloaded) == 1
        assert reloaded[0].model_dump(mode="json") == patterns[0].model_dump(mode="json")

    def test_round_trip_preserves_order(self, tmp_path: Path) -> None:
        a = build_pattern().model_copy(update={"id": "pattern-a"})
        b = build_pattern().model_copy(update={"id": "pattern-b"})
        path = tmp_path / "corpus.jsonl"

        save_corpus([a, b], path)
        reloaded = load_corpus(path)

        assert [p.id for p in reloaded] == ["pattern-a", "pattern-b"]

    def test_save_is_deterministic_across_repeated_writes(self, tmp_path: Path) -> None:
        patterns = [build_pattern()]
        path = tmp_path / "corpus.jsonl"

        save_corpus(patterns, path)
        first_bytes = path.read_bytes()
        save_corpus(patterns, path)
        second_bytes = path.read_bytes()

        assert first_bytes == second_bytes

    def test_save_writes_one_line_per_pattern(self, tmp_path: Path) -> None:
        patterns = [
            build_pattern().model_copy(update={"id": "a"}),
            build_pattern().model_copy(update={"id": "b"}),
        ]
        path = tmp_path / "corpus.jsonl"

        save_corpus(patterns, path)

        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert len(lines) == 2

    def test_save_creates_parent_directories(self, tmp_path: Path) -> None:
        path = tmp_path / "nested" / "dir" / "corpus.jsonl"

        save_corpus([build_pattern()], path)

        assert path.is_file()

    def test_load_skips_blank_lines(self, tmp_path: Path) -> None:
        pattern = build_pattern()
        path = tmp_path / "corpus.jsonl"
        path.write_text(
            f"\n{pattern.model_dump_json(exclude={'training_eligible'})}\n\n",
            encoding="utf-8",
        )

        reloaded = load_corpus(path)

        assert len(reloaded) == 1

    def test_load_empty_file_returns_empty_list(self, tmp_path: Path) -> None:
        path = tmp_path / "corpus.jsonl"
        path.write_text("", encoding="utf-8")

        assert load_corpus(path) == []


class TestLoadMalformedInput:
    def test_missing_file_raises_clear_cloudforge_error(self, tmp_path: Path) -> None:
        missing = tmp_path / "does-not-exist.jsonl"

        with pytest.raises(CorpusLoadError) as exc_info:
            load_corpus(missing)

        assert isinstance(exc_info.value, CloudforgeError)
        assert "does-not-exist.jsonl" in str(exc_info.value)

    def test_invalid_json_line_raises_clear_error_with_line_number(self, tmp_path: Path) -> None:
        path = tmp_path / "corpus.jsonl"
        path.write_text("{not valid json\n", encoding="utf-8")

        with pytest.raises(CorpusLoadError) as exc_info:
            load_corpus(path)

        assert ":1:" in str(exc_info.value)

    def test_non_object_json_line_raises_clear_error(self, tmp_path: Path) -> None:
        path = tmp_path / "corpus.jsonl"
        path.write_text("[1, 2, 3]\n", encoding="utf-8")

        with pytest.raises(CorpusLoadError, match="expected a JSON object"):
            load_corpus(path)

    def test_valid_json_but_invalid_riskpattern_raises_clear_error(self, tmp_path: Path) -> None:
        path = tmp_path / "corpus.jsonl"
        path.write_text('{"id": "incomplete"}\n', encoding="utf-8")

        with pytest.raises(CorpusLoadError, match="invalid RiskPattern"):
            load_corpus(path)

    def test_second_line_error_reports_correct_line_number(self, tmp_path: Path) -> None:
        pattern = build_pattern()
        path = tmp_path / "corpus.jsonl"
        good_line = pattern.model_dump_json(exclude={"training_eligible"})
        path.write_text(f"{good_line}\nnot json at all\n", encoding="utf-8")

        with pytest.raises(CorpusLoadError, match=r":2:"):
            load_corpus(path)


# --- validate_corpus: clean corpus passes ---------------------------------------------


class TestValidateCorpusCleanPasses:
    def test_single_clean_pattern_passes(self) -> None:
        report = validate_corpus([build_pattern()])
        assert report.passed
        assert report.issues == []
        assert isinstance(report, CorpusValidationReport)

    def test_empty_corpus_passes(self) -> None:
        report = validate_corpus([])
        assert report.passed
        assert report.pattern_count == 0

    def test_multiple_distinct_clean_patterns_pass(self) -> None:
        a = build_pattern().model_copy(update={"id": "a"})
        b = build_pattern().model_copy(update={"id": "b"})
        report = validate_corpus([a, b])
        assert report.passed


# --- violation: duplicate id -----------------------------------------------------------


class TestDuplicateIdDetected:
    def test_two_patterns_sharing_an_id_fail(self) -> None:
        a = build_pattern().model_copy(update={"id": "dup-id"})
        b = build_pattern().model_copy(update={"id": "dup-id"})

        report = validate_corpus([a, b])

        assert not report.passed
        assert any(issue.check == "unique_id" for issue in report.issues)
        assert any("dup-id" in issue.message for issue in report.issues)

    def test_duplicate_id_issue_names_both_occurrences_once(self) -> None:
        a = build_pattern().model_copy(update={"id": "dup-id"})
        b = build_pattern().model_copy(update={"id": "dup-id"})

        report = validate_corpus([a, b])

        dupe_issues = [i for i in report.issues if i.check == "unique_id"]
        assert len(dupe_issues) == 1

    def test_three_way_id_collision_is_detected(self) -> None:
        patterns = [build_pattern().model_copy(update={"id": "same"}) for _ in range(3)]

        report = validate_corpus(patterns)

        assert not report.passed
        assert any(i.check == "unique_id" for i in report.issues)


# --- violation: missing / incomplete provenance ----------------------------------------


class TestMissingProvenanceDetected:
    def test_blank_provenance_field_fails(self) -> None:
        pattern = build_pattern()
        bad_provenance = pattern.provenance.model_copy(update={"source_id": ""})
        pattern = pattern.model_copy(update={"provenance": bad_provenance})

        report = validate_corpus([pattern])

        assert not report.passed
        issue = next(i for i in report.issues if i.check == "provenance_complete")
        assert "source_id" in issue.message

    def test_blank_adapter_name_fails(self) -> None:
        pattern = build_pattern()
        bad_provenance = pattern.provenance.model_copy(update={"adapter_name": "   "})
        pattern = pattern.model_copy(update={"provenance": bad_provenance})

        report = validate_corpus([pattern])

        assert not report.passed
        issue = next(i for i in report.issues if i.check == "provenance_complete")
        assert "adapter_name" in issue.message

    def test_blank_notes_is_allowed(self) -> None:
        pattern = build_pattern()
        provenance = pattern.provenance.model_copy(update={"notes": ""})
        pattern = pattern.model_copy(update={"provenance": provenance})

        report = validate_corpus([pattern])

        assert report.passed


# --- violation: fragment fails validation (reuses validate_fragment) ------------------


class TestFragmentValidationReused:
    def test_fragment_with_forbidden_action_fails_corpus_validation(self) -> None:
        tags = NodeTags(env="prod", owner="team", app="analytics")
        security = NodeSecurity(criticality="medium")
        node = GraphNode(
            id="pol-1",
            type=NodeType.IAM_POLICY,
            name="pol-1",
            tags=tags,
            security=security,
            attributes={"actions": ["iam:DeleteRole"]},
        )
        fragment = ScenarioGraph(nodes=[node], edges=[])
        pattern = build_pattern().model_copy(
            update={"graph_fragment": fragment, "expected_findings": []}
        )

        report = validate_corpus([pattern])

        assert not report.passed
        issue = next(i for i in report.issues if i.check == "fragment_valid")
        assert "iam:DeleteRole" in issue.message

    def test_fragment_check_reuses_validate_fragment_reasons(self) -> None:
        # A finding referencing a missing resource is a validate_fragment rule-3 failure;
        # the message should carry the same reason text validate.validation_reasons emits.
        from app.cloudforge.models.findings import ExpectedFinding, FindingFamily

        pattern = build_pattern()
        bad_finding = ExpectedFinding(
            id="f-bad",
            severity="high",
            family=FindingFamily.S3_PUBLIC_EXPOSURE,
            resource_ids=["does-not-exist"],
            expected_scanner_visibility="visible",
            ground_truth="bogus",
            remediation="n/a",
        )
        pattern = pattern.model_copy(update={"expected_findings": [bad_finding]})

        report = validate_corpus([pattern])

        issue = next(i for i in report.issues if i.check == "fragment_valid")
        assert "f-bad" in issue.message
        assert "does-not-exist" in issue.message

    def test_clean_fragment_passes(self) -> None:
        pattern = build_pattern().model_copy(update={"graph_fragment": build_fragment()})
        report = validate_corpus([pattern])
        assert report.passed


# --- violation: unsafe_operational present --------------------------------------------


class TestUnsafeOperationalDetected:
    def test_unsafe_operational_pattern_fails(self) -> None:
        pattern = build_pattern(safety_classification=SafetyClassification.UNSAFE_OPERATIONAL)

        report = validate_corpus([pattern])

        assert not report.passed
        issue = next(i for i in report.issues if i.check == "no_unsafe_operational")
        assert "unsafe_operational" in issue.message

    def test_other_safety_classifications_do_not_trigger_this_check(self) -> None:
        for classification in (
            SafetyClassification.DEFENSIVE_PATTERN,
            SafetyClassification.BENCHMARK_PATTERN,
            SafetyClassification.TRAINING_PATTERN,
            SafetyClassification.RESTRICTED_SOURCE,
            SafetyClassification.UNKNOWN,
        ):
            pattern = build_pattern(safety_classification=classification)
            report = validate_corpus([pattern])
            assert not any(i.check == "no_unsafe_operational" for i in report.issues)


# --- violation: training_eligible inconsistent with its own stored fields -------------


class TestTrainingEligibleConsistencyDetected:
    def test_consistent_training_eligible_true_passes(self) -> None:
        pattern = build_pattern(
            validation_status=ValidationStatus.VALID,
            safety_classification=SafetyClassification.DEFENSIVE_PATTERN,
            reuse_status=ReuseStatus.FULL_REUSE,
            allowed_for_training=True,
        )
        assert pattern.training_eligible is True

        report = validate_corpus([pattern])

        assert not any(i.check == "training_eligible_consistent" for i in report.issues)

    def test_consistent_training_eligible_false_passes(self) -> None:
        pattern = build_pattern(
            validation_status=ValidationStatus.INVALID,
            safety_classification=SafetyClassification.DEFENSIVE_PATTERN,
        )
        assert pattern.training_eligible is False

        report = validate_corpus([pattern])

        assert not any(i.check == "training_eligible_consistent" for i in report.issues)

    def test_bypassed_validator_pattern_with_stale_training_eligible_is_detected(self) -> None:
        # model_construct bypasses field validation entirely. Substituting a bare str
        # ("valid") for the top-level validation_status field (keeping every nested
        # model, e.g. provenance, as the same real, already-validated instance) means the
        # `is ValidationStatus.VALID` identity check inside training_eligible silently
        # evaluates to False even though the stored string says "valid". This is exactly
        # the "stored inconsistency" design §9.5 requires detecting.
        clean = build_pattern(
            validation_status=ValidationStatus.VALID,
            safety_classification=SafetyClassification.DEFENSIVE_PATTERN,
            reuse_status=ReuseStatus.FULL_REUSE,
            allowed_for_training=True,
        )
        data = dict(clean.__dict__)
        data.pop("training_eligible", None)
        data["validation_status"] = "valid"  # raw string, not the enum member
        tampered = RiskPattern.model_construct(**data)

        assert tampered.training_eligible is False  # the latent bug this check catches

        report = validate_corpus([tampered])

        assert not report.passed
        issue = next(i for i in report.issues if i.check == "training_eligible_consistent")
        assert "training_eligible=False" in issue.message
        assert "expected=True" in issue.message


# --- multiple simultaneous violations reported together --------------------------------


class TestMultipleViolationsAllReported:
    def test_corpus_with_every_violation_type_reports_each(self) -> None:
        # Duplicate ids.
        dup_a = build_pattern().model_copy(update={"id": "dup"})
        dup_b = build_pattern().model_copy(update={"id": "dup"})
        # Missing provenance.
        no_prov = build_pattern().model_copy(update={"id": "no-prov"})
        no_prov = no_prov.model_copy(
            update={"provenance": no_prov.provenance.model_copy(update={"source_id": ""})}
        )
        # Unsafe operational.
        unsafe = build_pattern(safety_classification=SafetyClassification.UNSAFE_OPERATIONAL)
        unsafe = unsafe.model_copy(update={"id": "unsafe"})

        report = validate_corpus([dup_a, dup_b, no_prov, unsafe])

        checks_seen = {issue.check for issue in report.issues}
        assert "unique_id" in checks_seen
        assert "provenance_complete" in checks_seen
        assert "no_unsafe_operational" in checks_seen
        assert not report.passed
        assert report.pattern_count == 4
