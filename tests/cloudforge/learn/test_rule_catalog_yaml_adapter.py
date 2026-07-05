"""``rule_catalog_yaml`` adapter tests (FXL-63).

Exercises the adapter against the small fixture catalog
(``fixtures/sample_rule_catalog.yaml``, 4 entries: 2 AWS + 2 GCP, spanning storage/iam/
encryption domains) plus the malformed-catalog error paths. No internet, no ML.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.cloudforge.errors import CloudforgeError
from app.cloudforge.learn.adapters.rule_catalog_yaml import (
    ADAPTER_NAME,
    ADAPTER_VERSION,
    RuleCatalogYamlAdapter,
)
from app.cloudforge.learn.pattern_models import CloudProvider
from app.cloudforge.learn.source_models import ReuseStatus, SourceEntry, SourceType

_FIXTURES = Path(__file__).parent / "fixtures"


def _source_entry(**overrides: object) -> SourceEntry:
    base: dict[str, object] = {
        "id": "local-rule-catalog",
        "name": "cloudforge local curated rule catalog (seed patterns)",
        "type": SourceType.LOCAL_RULE_CATALOG,
        "path": "data/rule_catalog/seed_patterns.yaml",
        "adapter": "rule_catalog_yaml",
        "enabled": True,
        "license": "CC0-1.0",
        "reuse_status": ReuseStatus.FULL_REUSE,
        "allowed_for_training": True,
    }
    base.update(overrides)
    return SourceEntry.model_validate(base)


class TestExtract:
    def test_returns_one_record_per_catalog_entry(self) -> None:
        adapter = RuleCatalogYamlAdapter()
        records = adapter.extract(_source_entry(), _FIXTURES / "sample_rule_catalog.yaml")
        assert len(records) == 4
        assert {r.raw_id for r in records} == {
            "s3-public-read-aws-001",
            "iam-passrole-wildcard-aws-002",
            "gcs-public-bucket-gcp-003",
            "kms-key-no-rotation-gcp-004",
        }

    def test_field_mapping_is_correct(self) -> None:
        adapter = RuleCatalogYamlAdapter()
        records = adapter.extract(_source_entry(), _FIXTURES / "sample_rule_catalog.yaml")
        record = next(r for r in records if r.raw_id == "s3-public-read-aws-001")

        assert record.source_id == "local-rule-catalog"
        assert record.title == "Public-read S3 bucket"
        assert record.summary == "An S3 bucket is world-readable via a public-read ACL."
        assert record.cloud_provider is CloudProvider.AWS
        assert record.resource_types == ["aws_s3_bucket"]
        assert record.severity == "high"
        assert record.category == "storage"  # first domain
        assert record.remediation.startswith("Enable S3 Block Public Access")
        assert record.references == [
            "https://docs.aws.amazon.com/AmazonS3/latest/userguide/"
            "access-control-block-public-access.html"
        ]
        assert record.raw_payload["id"] == "s3-public-read-aws-001"
        assert record.raw_payload["domains"] == ["storage", "data"]

    def test_gcp_entry_maps_provider_and_domain(self) -> None:
        adapter = RuleCatalogYamlAdapter()
        records = adapter.extract(_source_entry(), _FIXTURES / "sample_rule_catalog.yaml")
        record = next(r for r in records if r.raw_id == "gcs-public-bucket-gcp-003")
        assert record.cloud_provider is CloudProvider.GCP
        assert record.category == "storage"
        assert record.resource_types == ["google_storage_bucket"]

    def test_provenance_is_complete_on_every_record(self) -> None:
        adapter = RuleCatalogYamlAdapter()
        records = adapter.extract(_source_entry(), _FIXTURES / "sample_rule_catalog.yaml")
        for record in records:
            prov = record.provenance
            assert prov.adapter_name == ADAPTER_NAME == "rule_catalog_yaml"
            assert prov.adapter_version == ADAPTER_VERSION
            assert prov.source_id == "local-rule-catalog"
            assert prov.source_type == SourceType.LOCAL_RULE_CATALOG
            assert prov.source_license == "CC0-1.0"
            assert prov.reuse_status == ReuseStatus.FULL_REUSE
            assert prov.allowed_for_training is True
            assert prov.extraction_method == "yaml_parse"
            assert prov.confidence == pytest.approx(0.75)
            assert prov.content_hash  # non-empty, stamped
            assert isinstance(prov.extracted_at, datetime)
            assert isinstance(prov.fetched_at, datetime)

    def test_content_hash_is_stable_for_same_file(self) -> None:
        adapter = RuleCatalogYamlAdapter()
        records_a = adapter.extract(_source_entry(), _FIXTURES / "sample_rule_catalog.yaml")
        records_b = adapter.extract(_source_entry(), _FIXTURES / "sample_rule_catalog.yaml")
        assert records_a[0].provenance.content_hash == records_b[0].provenance.content_hash

    def test_provenance_reflects_source_entry_overrides(self) -> None:
        adapter = RuleCatalogYamlAdapter()
        source = _source_entry(
            license="MIT",
            reuse_status=ReuseStatus.ATTRIBUTION,
            allowed_for_training=False,
        )
        records = adapter.extract(source, _FIXTURES / "sample_rule_catalog.yaml")
        for record in records:
            assert record.provenance.source_license == "MIT"
            assert record.provenance.reuse_status == ReuseStatus.ATTRIBUTION
            assert record.provenance.allowed_for_training is False

    def test_accepts_explicit_extracted_at(self) -> None:
        adapter = RuleCatalogYamlAdapter()
        stamp = datetime(2026, 1, 1, tzinfo=UTC)
        records = adapter.extract(
            _source_entry(), _FIXTURES / "sample_rule_catalog.yaml", extracted_at=stamp
        )
        assert all(r.provenance.extracted_at == stamp for r in records)


class TestErrorHandling:
    def test_missing_catalog_file_raises_cloudforge_error(self) -> None:
        adapter = RuleCatalogYamlAdapter()
        with pytest.raises(CloudforgeError):
            adapter.extract(_source_entry(), _FIXTURES / "does-not-exist.yaml")

    def test_malformed_yaml_raises_cloudforge_error(self) -> None:
        adapter = RuleCatalogYamlAdapter()
        with pytest.raises(CloudforgeError):
            adapter.extract(_source_entry(), _FIXTURES / "malformed_rule_catalog_bad_yaml.yaml")

    def test_missing_required_field_raises_cloudforge_error(self) -> None:
        adapter = RuleCatalogYamlAdapter()
        with pytest.raises(CloudforgeError):
            adapter.extract(
                _source_entry(), _FIXTURES / "malformed_rule_catalog_missing_field.yaml"
            )

    def test_top_level_not_a_catalog_raises_cloudforge_error(self, tmp_path: Path) -> None:
        bad = tmp_path / "not_a_catalog.yaml"
        bad.write_text("just_a_string: true\n", encoding="utf-8")
        with pytest.raises(CloudforgeError):
            RuleCatalogYamlAdapter().extract(_source_entry(), bad)

    def test_non_mapping_entry_raises_cloudforge_error(self, tmp_path: Path) -> None:
        bad = tmp_path / "list_entry.yaml"
        bad.write_text("entries:\n  - just a string\n", encoding="utf-8")
        with pytest.raises(CloudforgeError):
            RuleCatalogYamlAdapter().extract(_source_entry(), bad)

    def test_null_extra_field_is_coerced_to_empty_string_in_raw_payload(
        self, tmp_path: Path
    ) -> None:
        catalog = tmp_path / "null_extra_field.yaml"
        catalog.write_text(
            "entries:\n"
            "  - id: e-1\n"
            "    title: t\n"
            "    cloud_provider: aws\n"
            "    severity: low\n"
            "    license: null\n",
            encoding="utf-8",
        )
        records = RuleCatalogYamlAdapter().extract(_source_entry(), catalog)
        assert records[0].raw_payload["license"] == ""
