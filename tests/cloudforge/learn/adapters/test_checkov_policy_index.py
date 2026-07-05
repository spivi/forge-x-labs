"""``checkov_policy_index`` adapter tests: fixture-driven, metadata-only extraction.

No internet, no live Checkov/OPA — everything runs off the recorded fixture HTML under
``tests/cloudforge/learn/fixtures/``. See design §8 and §3 (Tier 1).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.cloudforge.learn.adapters.checkov_policy_index import (
    CheckovParseError,
    CheckovPolicyIndexAdapter,
    _cloud_provider_for,
)
from app.cloudforge.learn.pattern_models import CloudProvider, RawPatternRecord
from app.cloudforge.learn.registry import load_registry
from app.cloudforge.learn.source_models import ReuseStatus, SourceEntry, SourceType

FIXTURES = Path("tests/cloudforge/learn/fixtures")
SAMPLE_HTML = FIXTURES / "checkov_terraform_index_sample.html"
EMPTY_HTML = FIXTURES / "checkov_terraform_index_empty.html"
MALFORMED_HTML = FIXTURES / "checkov_terraform_index_malformed.html"

# The exact policy titles from the fixture, so tests can assert none of the "rule
# source" prohibition is violated while still confirming real content was extracted.
_FIXTURE_CHECK_IDS = {
    "CKV_AWS_18",
    "CKV_AWS_19",
    "CKV_AWS_20",
    "CKV_AWS_24",
    "CKV_AWS_260",
    "CKV_AWS_33",
    "CKV_AWS_17",
    "CKV_AWS_36",
    "CKV_AWS_35",
    "CKV_AWS_67",
    "CKV_AZURE_35",
    "CKV_GCP_62",
}

# Strings that must NEVER appear in an extracted record — standing in for "rule
# source/logic" (e.g. the kind of Python/Rego a real Checkov check body would contain).
_FORBIDDEN_RULE_SOURCE_SNIPPETS = (
    "def scan_resource_conf",
    "CheckResult.FAILED",
    "class Check(",
    "import checkov",
)


@pytest.fixture
def source_entry() -> SourceEntry:
    registry = load_registry(Path("data/source_registry.yaml"))
    entry = registry.by_id("checkov-terraform-index")
    assert entry is not None
    return entry


@pytest.fixture
def adapter() -> CheckovPolicyIndexAdapter:
    return CheckovPolicyIndexAdapter()


def test_adapter_identity(adapter: CheckovPolicyIndexAdapter) -> None:
    assert adapter.adapter_name == "checkov_policy_index"
    assert adapter.adapter_version


def test_extract_returns_one_record_per_table_row(
    adapter: CheckovPolicyIndexAdapter, source_entry: SourceEntry
) -> None:
    records = adapter.extract(source_entry, SAMPLE_HTML)

    assert len(records) == len(_FIXTURE_CHECK_IDS)
    assert {r.rule_id for r in records} == _FIXTURE_CHECK_IDS


def test_records_carry_metadata_fields(
    adapter: CheckovPolicyIndexAdapter, source_entry: SourceEntry
) -> None:
    records = adapter.extract(source_entry, SAMPLE_HTML)
    by_id = {r.rule_id: r for r in records}

    s3_public = by_id["CKV_AWS_20"]
    assert s3_public.resource_types == ["aws_s3_bucket"]
    assert "public" in s3_public.title.lower() or "read" in s3_public.title.lower()
    assert s3_public.severity == "critical"
    assert s3_public.cloud_provider is CloudProvider.AWS
    assert s3_public.source_id == "checkov-terraform-index"
    assert any("CKV_AWS_20" in ref for ref in s3_public.references)


def test_azure_and_gcp_rows_map_to_correct_cloud_provider(
    adapter: CheckovPolicyIndexAdapter, source_entry: SourceEntry
) -> None:
    records = adapter.extract(source_entry, SAMPLE_HTML)
    by_id = {r.rule_id: r for r in records}

    assert by_id["CKV_AZURE_35"].cloud_provider is CloudProvider.AZURE
    assert by_id["CKV_GCP_62"].cloud_provider is CloudProvider.GCP


def test_provenance_is_metadata_only_and_not_training_eligible(
    adapter: CheckovPolicyIndexAdapter, source_entry: SourceEntry
) -> None:
    records = adapter.extract(source_entry, SAMPLE_HTML)

    for record in records:
        prov = record.provenance
        assert prov.adapter_name == "checkov_policy_index"
        assert prov.adapter_version == adapter.adapter_version
        assert prov.reuse_status is ReuseStatus.METADATA_ONLY
        assert prov.allowed_for_training is False
        assert prov.confidence == pytest.approx(0.55)
        assert prov.content_hash
        assert prov.source_id == "checkov-terraform-index"
        assert prov.source_type is SourceType.SCANNER_RULE_INDEX
        assert prov.extraction_method
        assert prov.fetched_at is not None
        assert prov.extracted_at is not None


def test_content_hash_is_stable_for_same_fixture_bytes(
    adapter: CheckovPolicyIndexAdapter, source_entry: SourceEntry
) -> None:
    first = adapter.extract(source_entry, SAMPLE_HTML)
    second = adapter.extract(source_entry, SAMPLE_HTML)

    assert first[0].provenance.content_hash == second[0].provenance.content_hash


def test_no_rule_source_code_leaks_into_any_record(
    adapter: CheckovPolicyIndexAdapter, source_entry: SourceEntry
) -> None:
    records = adapter.extract(source_entry, SAMPLE_HTML)

    for record in records:
        haystack = " ".join(
            [
                record.title,
                record.summary,
                record.remediation,
                " ".join(record.references),
                " ".join(str(v) for v in record.raw_payload.values()),
            ]
        )
        for snippet in _FORBIDDEN_RULE_SOURCE_SNIPPETS:
            assert snippet not in haystack


def test_raw_payload_never_contains_rule_logic_keys(
    adapter: CheckovPolicyIndexAdapter, source_entry: SourceEntry
) -> None:
    records = adapter.extract(source_entry, SAMPLE_HTML)

    forbidden_keys = {"rule_source", "source_code", "logic", "check_body"}
    for record in records:
        assert not (set(record.raw_payload) & forbidden_keys)


def test_empty_html_returns_empty_list(
    adapter: CheckovPolicyIndexAdapter, source_entry: SourceEntry
) -> None:
    records = adapter.extract(source_entry, EMPTY_HTML)
    assert records == []


def test_malformed_html_does_not_crash(
    adapter: CheckovPolicyIndexAdapter, source_entry: SourceEntry
) -> None:
    # html.parser is lenient with unclosed tags; the adapter must not raise on this
    # input, and it must not fabricate a record for the truncated dangling row.
    records = adapter.extract(source_entry, MALFORMED_HTML)
    assert isinstance(records, list)


def test_missing_fixture_file_raises_parse_error(
    adapter: CheckovPolicyIndexAdapter, source_entry: SourceEntry
) -> None:
    with pytest.raises(CheckovParseError):
        adapter.extract(source_entry, FIXTURES / "does-not-exist.html")


def test_cloud_provider_for_unrecognized_prefix_falls_back_to_generic() -> None:
    # No fixture row hits this (the real Checkov index has no such prefix), but the
    # adapter must degrade gracefully rather than raise for a future/unknown vendor.
    assert _cloud_provider_for("CKV_UNKNOWNVENDOR_1") is CloudProvider.GENERIC


def test_every_record_is_a_valid_raw_pattern_record(
    adapter: CheckovPolicyIndexAdapter, source_entry: SourceEntry
) -> None:
    records = adapter.extract(source_entry, SAMPLE_HTML)
    for record in records:
        # round-trips through the real pydantic model with no coercion surprises.
        assert RawPatternRecord.model_validate(record.model_dump()) == record
