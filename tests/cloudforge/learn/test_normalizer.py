"""``PatternNormalizer`` tests (FXL-66): ``RawPatternRecord`` -> ``RiskPattern``.

Exercises the normalizer against real records produced by all three adapters
(``cloudforge_scenario``, ``rule_catalog_yaml``, ``checkov_policy_index``) — no
hand-waved/synthetic records for the adapter-shape coverage. Determinism, provenance
completeness, and the unsafe-content safety scan get dedicated unit tests using
lighter hand-built records for precise control over inputs.

No internet, no ML, no embeddings — pure deterministic field mapping.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.cloudforge.errors import CloudforgeError
from app.cloudforge.learn.adapters.checkov_policy_index import CheckovPolicyIndexAdapter
from app.cloudforge.learn.adapters.cloudforge_scenario import CloudforgeScenarioAdapter
from app.cloudforge.learn.adapters.rule_catalog_yaml import RuleCatalogYamlAdapter
from app.cloudforge.learn.normalizer import NORMALIZER_VERSION, PatternNormalizer
from app.cloudforge.learn.pattern_enums import SafetyClassification, ValidationStatus
from app.cloudforge.learn.pattern_models import PatternProvenance, RawPatternRecord
from app.cloudforge.learn.registry import load_registry
from app.cloudforge.learn.source_models import ReuseStatus, SourceEntry, SourceType
from app.cloudforge.models.graph import ScenarioGraph

_FIXTURES = Path("tests/cloudforge/learn/fixtures")
_CI_CD_DIR = _FIXTURES / "scenario_ci_cd_iam_chain"
_REGISTRY = Path("data/source_registry.yaml")
_TS = datetime(2026, 7, 5, 12, 0, 0, tzinfo=UTC)


def _local_rule_catalog_source() -> SourceEntry:
    registry = load_registry(_REGISTRY)
    entry = registry.by_id("local-rule-catalog")
    assert entry is not None
    return entry


def _checkov_source() -> SourceEntry:
    registry = load_registry(_REGISTRY)
    entry = registry.by_id("checkov-terraform-index")
    assert entry is not None
    return entry


def _scenario_source() -> SourceEntry:
    return SourceEntry(
        id="local-scenarios-out",
        name="cloudforge generated scenario dirs",
        type=SourceType.LOCAL_SCENARIO_DIR,
        path=str(_CI_CD_DIR),
        adapter="cloudforge_scenario",
        enabled=True,
        license="CC0-1.0",
        reuse_status=ReuseStatus.FULL_REUSE,
        allowed_for_training=True,
        notes="test",
    )


def _build_provenance(**overrides: object) -> PatternProvenance:
    base: dict[str, object] = {
        "source_id": "local-rule-catalog",
        "source_name": "cloudforge local curated rule catalog",
        "source_type": SourceType.LOCAL_RULE_CATALOG,
        "source_url_or_path": "data/rule_catalog/seed_patterns.yaml",
        "source_license": "CC0-1.0",
        "reuse_status": ReuseStatus.FULL_REUSE,
        "allowed_for_training": True,
        "extraction_method": "yaml_parse",
        "fetched_at": _TS,
        "extracted_at": _TS,
        "content_hash": "deadbeef",
        "adapter_name": "rule_catalog_yaml",
        "adapter_version": "0.1.0",
        "normalizer_version": "unset",
        "confidence": 0.75,
        "notes": "",
    }
    base.update(overrides)
    return PatternProvenance.model_validate(base)


def _build_raw(**overrides: object) -> RawPatternRecord:
    base: dict[str, object] = {
        "source_id": "local-rule-catalog",
        "raw_id": "s3-public-read-aws-001",
        "title": "Public-read S3 bucket",
        "summary": "An S3 bucket is world-readable via a public-read ACL.",
        "cloud_provider": "aws",
        "resource_types": ["aws_s3_bucket"],
        "rule_id": None,
        "severity": "high",
        "category": "storage",
        "remediation": "Enable S3 Block Public Access.",
        "references": ["https://example.com/s3"],
        "raw_payload": {},
        "provenance": _build_provenance(),
    }
    base.update(overrides)
    return RawPatternRecord.model_validate(base)


# --- basic field mapping ------------------------------------------------------


class TestFieldMapping:
    def test_normalize_maps_core_fields(self) -> None:
        raw = _build_raw()
        pattern = PatternNormalizer().normalize(raw)

        assert pattern.title == raw.title
        assert pattern.summary == raw.summary
        assert pattern.cloud_provider == raw.cloud_provider
        assert pattern.severity == raw.severity
        assert pattern.remediation == raw.remediation
        assert pattern.affected_resource_types == ["aws_s3_bucket"]

    def test_normalize_id_is_stable_slug_derived_from_source_and_raw_id(self) -> None:
        raw = _build_raw(source_id="local-rule-catalog", raw_id="s3-public-read-aws-001")
        pattern = PatternNormalizer().normalize(raw)

        assert pattern.id == "local-rule-catalog-s3-public-read-aws-001"

    def test_normalize_id_slugifies_non_alnum_raw_id(self) -> None:
        raw = _build_raw(source_id="checkov-terraform-index", raw_id="CKV_AWS_20")
        pattern = PatternNormalizer().normalize(raw)

        assert pattern.id == "checkov-terraform-index-ckv-aws-20"

    def test_normalize_sorts_list_fields(self) -> None:
        raw = _build_raw(resource_types=["aws_s3_bucket", "aws_iam_role"])
        pattern = PatternNormalizer().normalize(raw)

        assert pattern.affected_resource_types == sorted(pattern.affected_resource_types)
        assert pattern.domains == sorted(pattern.domains, key=lambda d: d.value)

    def test_normalize_source_mappings_carries_rule_id(self) -> None:
        raw = _build_raw(rule_id="CKV_AWS_20")
        pattern = PatternNormalizer().normalize(raw)

        assert pattern.source_mappings == ["CKV_AWS_20"]

    def test_normalize_missing_rule_id_gives_empty_source_mappings(self) -> None:
        raw = _build_raw(rule_id=None)
        pattern = PatternNormalizer().normalize(raw)

        assert pattern.source_mappings == []

    def test_normalize_missing_cloud_provider_defaults_to_generic(self) -> None:
        raw = _build_raw(cloud_provider=None)
        pattern = PatternNormalizer().normalize(raw)

        assert pattern.cloud_provider.value == "generic"

    def test_normalize_missing_severity_defaults_to_medium(self) -> None:
        raw = _build_raw(severity=None)
        pattern = PatternNormalizer().normalize(raw)

        assert pattern.severity == "medium"

    def test_normalize_confidence_carries_adapter_default(self) -> None:
        raw = _build_raw(provenance=_build_provenance(confidence=0.75))
        pattern = PatternNormalizer().normalize(raw)

        assert pattern.confidence == pytest.approx(0.75)


# --- domains / weakness_family inference --------------------------------------


class TestDomainAndWeaknessInference:
    def test_category_matching_domain_value_is_used(self) -> None:
        raw = _build_raw(category="iam", resource_types=[])
        pattern = PatternNormalizer().normalize(raw)

        assert pattern.domains == [pattern.domains[0]]
        assert pattern.domains[0].value == "iam"

    def test_storage_resource_type_infers_storage_domain(self) -> None:
        raw = _build_raw(category=None, resource_types=["aws_s3_bucket"])
        pattern = PatternNormalizer().normalize(raw)

        assert any(d.value == "storage" for d in pattern.domains)

    def test_no_signal_falls_back_to_governance_domain(self) -> None:
        raw = _build_raw(category=None, resource_types=[], title="Unspecified risk", summary="")
        pattern = PatternNormalizer().normalize(raw)

        assert pattern.domains == [pattern.domains[0]]
        assert pattern.domains[0].value == "governance"

    def test_weakness_family_defaults_to_other_without_signal(self) -> None:
        raw = _build_raw(category=None, resource_types=[], title="Unspecified risk", summary="")
        pattern = PatternNormalizer().normalize(raw)

        assert pattern.weakness_family.value == "other"

    def test_weakness_family_infers_public_exposure_from_title(self) -> None:
        raw = _build_raw(title="Publicly readable bucket", summary="allows public access")
        pattern = PatternNormalizer().normalize(raw)

        assert pattern.weakness_family.value in {"public_exposure", "s3_public_exposure"}


# --- graph fragment construction ----------------------------------------------


class TestGraphFragment:
    def test_normalize_builds_minimal_fragment_from_resource_types(self) -> None:
        raw = _build_raw(resource_types=["aws_s3_bucket", "aws_iam_role"])
        pattern = PatternNormalizer().normalize(raw)

        assert isinstance(pattern.graph_fragment, ScenarioGraph)
        assert len(pattern.graph_fragment.nodes) >= 1

    def test_normalize_empty_resource_types_gives_empty_but_valid_fragment(self) -> None:
        raw = _build_raw(resource_types=[])
        pattern = PatternNormalizer().normalize(raw)

        assert pattern.graph_fragment.nodes == []
        assert pattern.graph_fragment.edges == []

    def test_normalize_reuses_real_scenario_graph_from_raw_payload(self) -> None:
        adapter = CloudforgeScenarioAdapter()
        records = adapter.extract(_scenario_source(), _CI_CD_DIR)
        pattern = PatternNormalizer().normalize(records[0])

        assert len(pattern.graph_fragment.nodes) > 2
        assert len(pattern.graph_fragment.edges) > 1
        node_ids = {n.id for n in pattern.graph_fragment.nodes}
        assert "cicd-github" in node_ids


# --- validation_status / normalizer_version -----------------------------------


class TestValidationStatusAndVersioning:
    def test_validation_status_is_always_unvalidated(self) -> None:
        raw = _build_raw()
        pattern = PatternNormalizer().normalize(raw)

        assert pattern.validation_status is ValidationStatus.UNVALIDATED

    def test_normalizer_version_is_pinned_into_provenance(self) -> None:
        raw = _build_raw()
        pattern = PatternNormalizer().normalize(raw)

        assert pattern.provenance.normalizer_version == NORMALIZER_VERSION
        assert NORMALIZER_VERSION != ""

    def test_training_eligible_is_derived_not_set_directly(self) -> None:
        # training_eligible is a computed_field on RiskPattern; the normalizer must
        # never try to pass it explicitly (it isn't a settable field at all).
        raw = _build_raw(
            provenance=_build_provenance(
                reuse_status=ReuseStatus.FULL_REUSE, allowed_for_training=True
            )
        )
        pattern = PatternNormalizer().normalize(raw)

        # unvalidated -> never eligible yet, regardless of otherwise-favorable provenance.
        assert pattern.training_eligible is False


# --- safety classification -----------------------------------------------------


class TestSafetyClassification:
    def test_metadata_only_reuse_gives_benchmark_pattern(self) -> None:
        raw = _build_raw(
            provenance=_build_provenance(
                reuse_status=ReuseStatus.METADATA_ONLY, allowed_for_training=False
            )
        )
        pattern = PatternNormalizer().normalize(raw)

        assert pattern.safety_classification is SafetyClassification.BENCHMARK_PATTERN

    def test_restricted_reuse_gives_restricted_source(self) -> None:
        raw = _build_raw(
            provenance=_build_provenance(
                reuse_status=ReuseStatus.RESTRICTED, allowed_for_training=False
            )
        )
        pattern = PatternNormalizer().normalize(raw)

        assert pattern.safety_classification is SafetyClassification.RESTRICTED_SOURCE

    def test_unknown_reuse_gives_restricted_source(self) -> None:
        raw = _build_raw(
            provenance=_build_provenance(
                reuse_status=ReuseStatus.UNKNOWN, allowed_for_training=False
            )
        )
        pattern = PatternNormalizer().normalize(raw)

        assert pattern.safety_classification is SafetyClassification.RESTRICTED_SOURCE

    def test_full_reuse_gives_defensive_pattern(self) -> None:
        raw = _build_raw(
            provenance=_build_provenance(
                reuse_status=ReuseStatus.FULL_REUSE, allowed_for_training=True
            )
        )
        pattern = PatternNormalizer().normalize(raw)

        assert pattern.safety_classification is SafetyClassification.DEFENSIVE_PATTERN

    def test_mappings_only_gives_benchmark_pattern(self) -> None:
        raw = _build_raw(
            provenance=_build_provenance(
                reuse_status=ReuseStatus.MAPPINGS_ONLY, allowed_for_training=True
            )
        )
        pattern = PatternNormalizer().normalize(raw)

        assert pattern.safety_classification is SafetyClassification.BENCHMARK_PATTERN

    @pytest.mark.parametrize(
        "field,value",
        [
            ("title", "How to escalate privilege via credential-theft exploit chain"),
            ("summary", "This describes a persistence backdoor and evasion technique"),
            ("remediation", "Deploy the malware payload for destructive-action testing"),
        ],
    )
    def test_unsafe_operational_keywords_override_classification(
        self, field: str, value: str
    ) -> None:
        raw = _build_raw(
            **{field: value},
            provenance=_build_provenance(
                reuse_status=ReuseStatus.FULL_REUSE, allowed_for_training=True
            ),
        )
        pattern = PatternNormalizer().normalize(raw)

        assert pattern.safety_classification is SafetyClassification.UNSAFE_OPERATIONAL

    def test_private_key_like_content_triggers_unsafe_operational(self) -> None:
        raw = _build_raw(summary="-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQ==\n")
        pattern = PatternNormalizer().normalize(raw)

        assert pattern.safety_classification is SafetyClassification.UNSAFE_OPERATIONAL

    def test_benign_content_does_not_trigger_unsafe_operational(self) -> None:
        raw = _build_raw(
            title="Public-read S3 bucket",
            summary="An S3 bucket is world-readable via a public-read ACL.",
            remediation="Enable S3 Block Public Access.",
        )
        pattern = PatternNormalizer().normalize(raw)

        assert pattern.safety_classification is not SafetyClassification.UNSAFE_OPERATIONAL


# --- provenance completeness ---------------------------------------------------


class TestProvenanceCompleteness:
    def test_incomplete_provenance_raises_cloudforge_error(self) -> None:
        incomplete = _build_provenance(source_name="", source_license="")
        raw = _build_raw(provenance=incomplete)

        with pytest.raises(CloudforgeError):
            PatternNormalizer().normalize(raw)

    def test_blank_content_hash_raises_cloudforge_error(self) -> None:
        incomplete = _build_provenance(content_hash="")
        raw = _build_raw(provenance=incomplete)

        with pytest.raises(CloudforgeError):
            PatternNormalizer().normalize(raw)

    def test_complete_provenance_does_not_raise(self) -> None:
        raw = _build_raw(provenance=_build_provenance())
        PatternNormalizer().normalize(raw)  # no raise

    def test_provenance_fields_are_stamped_completely(self) -> None:
        raw = _build_raw()
        pattern = PatternNormalizer().normalize(raw)

        prov = pattern.provenance
        assert prov.source_id == raw.provenance.source_id
        assert prov.source_name == raw.provenance.source_name
        assert prov.adapter_name == raw.provenance.adapter_name
        assert prov.content_hash == raw.provenance.content_hash
        assert prov.confidence == raw.provenance.confidence


# --- determinism ----------------------------------------------------------------


class TestDeterminism:
    def test_normalizing_same_record_twice_is_byte_identical(self) -> None:
        raw = _build_raw()
        normalizer = PatternNormalizer()

        first = normalizer.normalize(raw).model_dump(mode="json")
        second = PatternNormalizer().normalize(raw).model_dump(mode="json")

        assert first == second

    def test_normalizing_scenario_adapter_record_is_deterministic(self) -> None:
        adapter = CloudforgeScenarioAdapter()
        records = adapter.extract(_scenario_source(), _CI_CD_DIR)

        first = PatternNormalizer().normalize(records[0]).model_dump(mode="json")
        second = PatternNormalizer().normalize(records[0]).model_dump(mode="json")

        assert first == second


# --- cross-adapter integration ---------------------------------------------------


class TestAllThreeAdapters:
    def test_normalizes_cloudforge_scenario_record(self) -> None:
        adapter = CloudforgeScenarioAdapter()
        records = adapter.extract(_scenario_source(), _CI_CD_DIR)
        assert records

        pattern = PatternNormalizer().normalize(records[0])

        assert pattern.provenance.adapter_name == "cloudforge_scenario"
        assert pattern.validation_status is ValidationStatus.UNVALIDATED
        assert pattern.safety_classification is SafetyClassification.DEFENSIVE_PATTERN
        assert len(pattern.graph_fragment.nodes) > 0

    def test_normalizes_rule_catalog_yaml_record(self) -> None:
        adapter = RuleCatalogYamlAdapter()
        source = _local_rule_catalog_source()
        records = adapter.extract(source, _FIXTURES / "sample_rule_catalog.yaml")
        assert records

        pattern = PatternNormalizer().normalize(records[0])

        assert pattern.provenance.adapter_name == "rule_catalog_yaml"
        assert pattern.validation_status is ValidationStatus.UNVALIDATED
        assert pattern.safety_classification is SafetyClassification.DEFENSIVE_PATTERN
        assert pattern.affected_resource_types == sorted(pattern.affected_resource_types)

    def test_normalizes_checkov_policy_index_record(self) -> None:
        adapter = CheckovPolicyIndexAdapter()
        source = _checkov_source()
        fixture = _FIXTURES / "checkov_terraform_index_sample.html"
        records = adapter.extract(source, fixture)
        assert records

        pattern = PatternNormalizer().normalize(records[0])

        assert pattern.provenance.adapter_name == "checkov_policy_index"
        assert pattern.validation_status is ValidationStatus.UNVALIDATED
        # metadata_only -> benchmark_pattern (not training-eligible either way).
        assert pattern.safety_classification is SafetyClassification.BENCHMARK_PATTERN
        assert pattern.training_eligible is False

    def test_all_checkov_records_normalize_without_error(self) -> None:
        adapter = CheckovPolicyIndexAdapter()
        source = _checkov_source()
        fixture = _FIXTURES / "checkov_terraform_index_sample.html"
        records = adapter.extract(source, fixture)

        normalizer = PatternNormalizer()
        patterns = [normalizer.normalize(r) for r in records]

        assert len(patterns) == len(records)
        assert len({p.id for p in patterns}) == len(patterns)  # unique ids

    def test_all_rule_catalog_records_normalize_without_error(self) -> None:
        adapter = RuleCatalogYamlAdapter()
        source = _local_rule_catalog_source()
        records = adapter.extract(source, _FIXTURES / "sample_rule_catalog.yaml")

        normalizer = PatternNormalizer()
        patterns = [normalizer.normalize(r) for r in records]

        assert len(patterns) == len(records)
        assert all(p.validation_status is ValidationStatus.UNVALIDATED for p in patterns)
