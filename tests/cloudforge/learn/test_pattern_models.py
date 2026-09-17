"""RiskPattern / provenance model tests: round-trip + training_eligible truth table."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.cloudforge.learn.pattern_models import (
    CloudProvider,
    RawPatternRecord,
    RiskPattern,
    SafetyClassification,
    ValidationStatus,
    WeaknessFamily,
)
from app.cloudforge.learn.source_models import ReuseStatus
from app.cloudforge.models.graph import ScenarioGraph

from .conftest import build_pattern, build_provenance


def test_risk_pattern_round_trips_through_dump_and_validate(sample_pattern: RiskPattern) -> None:
    # training_eligible is a derived computed_field: it serializes out but is never an
    # input, so a faithful round-trip excludes it before re-validating.
    dumped = sample_pattern.model_dump(exclude={"training_eligible"})
    restored = RiskPattern.model_validate(dumped)

    assert restored == sample_pattern
    # graph_fragment survives as a real ScenarioGraph.
    assert isinstance(restored.graph_fragment, ScenarioGraph)
    assert restored.graph_fragment.edges[0].from_ == "app-1"
    assert restored.expected_findings[0].resource_ids == ["bucket-1"]


def test_weakness_family_reuses_finding_family_vocab() -> None:
    # The cloudforge families must share the FindingFamily string values.
    from app.cloudforge.models.findings import FindingFamily

    assert WeaknessFamily.S3_PUBLIC_EXPOSURE.value == FindingFamily.S3_PUBLIC_EXPOSURE.value
    assert WeaknessFamily.IAM_PASSROLE_RISK.value == FindingFamily.IAM_PASSROLE_RISK.value
    # And the generic families exist.
    assert WeaknessFamily.MISSING_ENCRYPTION.value == "missing_encryption"


def test_pattern_forbids_extra_fields(sample_pattern: RiskPattern) -> None:
    payload = {
        **sample_pattern.model_dump(exclude={"training_eligible"}),
        "surprise": "nope",
    }
    with pytest.raises(ValidationError, match="surprise"):
        RiskPattern.model_validate(payload)


def test_provenance_is_required() -> None:
    payload = build_pattern().model_dump(exclude={"training_eligible"})
    del payload["provenance"]
    with pytest.raises(ValidationError, match="provenance"):
        RiskPattern.model_validate(payload)


def test_raw_pattern_record_round_trips() -> None:
    record = RawPatternRecord(
        source_id="checkov-terraform-index",
        raw_id="CKV_AWS_20",
        title="S3 bucket should not allow public read",
        cloud_provider=CloudProvider.AWS,
        resource_types=["aws_s3_bucket"],
        rule_id="CKV_AWS_20",
        severity="high",
        provenance=build_provenance(
            reuse_status=ReuseStatus.METADATA_ONLY, allowed_for_training=False
        ),
    )
    assert RawPatternRecord.model_validate(record.model_dump()) == record


# --- training_eligible truth table (design §6) ---------------------


def test_training_eligible_valid_defensive_full_reuse_is_true() -> None:
    pattern = build_pattern(
        reuse_status=ReuseStatus.FULL_REUSE,
        allowed_for_training=True,
        validation_status=ValidationStatus.VALID,
        safety_classification=SafetyClassification.DEFENSIVE_PATTERN,
    )
    assert pattern.training_eligible is True


def test_training_eligible_mappings_only_allowed_is_true() -> None:
    # CCM control-ID mappings are training-eligible.
    pattern = build_pattern(
        reuse_status=ReuseStatus.MAPPINGS_ONLY,
        allowed_for_training=True,
        safety_classification=SafetyClassification.BENCHMARK_PATTERN,
    )
    assert pattern.training_eligible is True


def test_training_eligible_restricted_is_false() -> None:
    pattern = build_pattern(reuse_status=ReuseStatus.RESTRICTED, allowed_for_training=False)
    assert pattern.training_eligible is False


def test_training_eligible_metadata_only_is_false() -> None:
    pattern = build_pattern(reuse_status=ReuseStatus.METADATA_ONLY, allowed_for_training=False)
    assert pattern.training_eligible is False


def test_training_eligible_unknown_reuse_is_false() -> None:
    pattern = build_pattern(reuse_status=ReuseStatus.UNKNOWN, allowed_for_training=False)
    assert pattern.training_eligible is False


def test_training_eligible_unsafe_operational_is_false() -> None:
    pattern = build_pattern(safety_classification=SafetyClassification.UNSAFE_OPERATIONAL)
    assert pattern.training_eligible is False


def test_training_eligible_unvalidated_is_false() -> None:
    pattern = build_pattern(validation_status=ValidationStatus.UNVALIDATED)
    assert pattern.training_eligible is False


def test_training_eligible_allowed_flag_false_is_false() -> None:
    # full_reuse but provenance says not allowed -> not eligible.
    pattern = build_pattern(reuse_status=ReuseStatus.FULL_REUSE, allowed_for_training=False)
    assert pattern.training_eligible is False


def test_training_eligible_is_included_in_dump(sample_pattern: RiskPattern) -> None:
    # computed_field serializes into the dump so consumers see it.
    assert sample_pattern.model_dump()["training_eligible"] is True
