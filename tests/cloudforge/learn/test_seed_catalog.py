"""Seed rule catalog tests: the real ``data/rule_catalog/seed_patterns.yaml``.

Loads the actual seed catalog (not a fixture) through the merged ``rule_catalog_yaml``
adapter and the real source registry, and asserts (design §8):

- it parses into >=12 ``RawPatternRecord``s with complete provenance
- it spans an AWS / Azure / GCP provider mix
- it spans the required domains (iam, storage, network, logging, encryption, ci_cd,
  secrets, data) via the catalog's raw ``domains`` field
- every entry carries the required governance/safety fields (license, reuse_status,
  allowed_for_training) with our-own-defensive-seed values
- no entry contains operational-attack/exploit keywords, real-secret-shaped values, or
  live-looking (non-dummy) AWS account IDs

No internet, no ML — pure YAML + adapter parsing.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from app.cloudforge.constants import DUMMY_ACCOUNT_ID
from app.cloudforge.learn.adapters.rule_catalog_yaml import RuleCatalogYamlAdapter
from app.cloudforge.learn.pattern_models import CloudProvider, RawPatternRecord
from app.cloudforge.learn.registry import get_entry, load_registry
from app.cloudforge.learn.source_models import ReuseStatus

_REGISTRY_PATH = Path("data/source_registry.yaml")
_SOURCE_ID = "local-rule-catalog"
_MIN_ENTRIES = 12

_REQUIRED_DOMAINS = {
    "iam",
    "storage",
    "network",
    "logging",
    "encryption",
    "ci_cd",
    "secrets",
    "data",
}

# Operational attack/exploit vocabulary that must never appear in a defensive-only
# seed entry. Deliberately high-level/generic (design directive: no operational
# attack steps, no persistence/evasion). Matched case-insensitively as substrings.
_UNSAFE_KEYWORDS = (
    "exploit",
    "payload",
    "reverse shell",
    "privilege escalation exploit",
    "curl http",
    "wget http",
    "backdoor",
    "persistence technique",
    "lateral movement",
    "c2 ",
    "metasploit",
    "nmap ",
    "sqlmap",
)

# Real-secret-shaped substrings that must never appear in seed content.
_SECRET_PATTERNS = (
    re.compile(r"AKIA[0-9A-Z]{16}"),  # AWS access key id shape
    re.compile(r"(?i)-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)

# A 12-digit number that is NOT the project's dummy account id — treated as a
# live-looking AWS account id if it appears anywhere in the catalog text.
_ACCOUNT_ID_SHAPE = re.compile(r"\b\d{12}\b")


def _load_catalog_path() -> Path:
    registry = load_registry(_REGISTRY_PATH)
    entry = get_entry(registry, _SOURCE_ID)
    assert entry.path is not None
    return Path(entry.path)


def _load_records() -> list[RawPatternRecord]:
    registry = load_registry(_REGISTRY_PATH)
    entry = get_entry(registry, _SOURCE_ID)
    catalog_path = _load_catalog_path()
    return RuleCatalogYamlAdapter().extract(entry, catalog_path)


class TestSeedCatalogRegistryWiring:
    def test_registry_points_local_rule_catalog_at_the_seed_file(self) -> None:
        registry = load_registry(_REGISTRY_PATH)
        entry = get_entry(registry, _SOURCE_ID)
        assert entry.path == "data/rule_catalog/seed_patterns.yaml"
        assert entry.adapter == "rule_catalog_yaml"
        assert entry.enabled is True
        assert entry.license == "CC0-1.0"
        assert entry.reuse_status is ReuseStatus.FULL_REUSE
        assert entry.allowed_for_training is True

    def test_seed_catalog_file_exists_at_registry_path(self) -> None:
        catalog_path = _load_catalog_path()
        assert catalog_path == Path("data/rule_catalog/seed_patterns.yaml")
        assert catalog_path.is_file()


class TestSeedCatalogParsesViaRealAdapter:
    def test_parses_into_at_least_12_records(self) -> None:
        records = _load_records()
        assert len(records) >= _MIN_ENTRIES

    def test_every_record_id_is_unique(self) -> None:
        records = _load_records()
        ids = [r.raw_id for r in records]
        assert len(ids) == len(set(ids))

    def test_every_record_has_complete_provenance(self) -> None:
        records = _load_records()
        for record in records:
            prov = record.provenance
            assert prov.source_id == _SOURCE_ID
            assert prov.adapter_name == "rule_catalog_yaml"
            assert prov.source_license == "CC0-1.0"
            assert prov.reuse_status is ReuseStatus.FULL_REUSE
            assert prov.allowed_for_training is True
            assert prov.content_hash
            assert prov.confidence == 0.75

    def test_every_record_has_required_core_fields(self) -> None:
        records = _load_records()
        for record in records:
            assert record.raw_id
            assert record.title
            assert record.summary
            assert record.cloud_provider is not None
            assert record.resource_types
            assert record.severity is not None
            assert record.category  # first domain, non-empty
            assert record.remediation
            assert record.references

    def test_every_record_has_the_full_raw_payload_field_set(self) -> None:
        required_keys = {
            "id",
            "title",
            "summary",
            "cloud_provider",
            "domains",
            "weakness_family",
            "severity",
            "affected_resource_types",
            "risky_relationships",
            "missing_controls",
            "negative_controls",
            "compensating_controls",
            "remediation",
            "references",
            "license",
            "reuse_status",
            "allowed_for_training",
        }
        records = _load_records()
        for record in records:
            missing = required_keys - record.raw_payload.keys()
            assert not missing, f"{record.raw_id} missing raw fields: {missing}"
            assert record.raw_payload["license"] == "CC0-1.0"
            assert record.raw_payload["reuse_status"] == "full_reuse"
            assert record.raw_payload["allowed_for_training"] == "true"


class TestSeedCatalogCoverage:
    def test_spans_aws_azure_gcp_provider_mix(self) -> None:
        records = _load_records()
        providers = {r.cloud_provider for r in records}
        assert providers == {CloudProvider.AWS, CloudProvider.AZURE, CloudProvider.GCP}
        # a "mix" means more than a single token entry per non-AWS provider.
        assert sum(1 for r in records if r.cloud_provider is CloudProvider.AWS) >= 3
        assert sum(1 for r in records if r.cloud_provider is CloudProvider.AZURE) >= 1
        assert sum(1 for r in records if r.cloud_provider is CloudProvider.GCP) >= 1

    def test_spans_all_required_domains(self) -> None:
        raw = yaml.safe_load(_load_catalog_path().read_text(encoding="utf-8"))
        seen_domains: set[str] = set()
        for entry in raw["entries"]:
            seen_domains.update(entry.get("domains", []))
        missing = _REQUIRED_DOMAINS - seen_domains
        assert not missing, f"seed catalog missing domain coverage: {missing}"


class TestSeedCatalogSafety:
    def test_no_unsafe_operational_keywords(self) -> None:
        text = _load_catalog_path().read_text(encoding="utf-8").lower()
        hits = [kw for kw in _UNSAFE_KEYWORDS if kw in text]
        assert not hits, f"seed catalog contains unsafe operational keywords: {hits}"

    def test_no_real_secret_shaped_values(self) -> None:
        text = _load_catalog_path().read_text(encoding="utf-8")
        for pattern in _SECRET_PATTERNS:
            assert not pattern.search(text), (
                f"seed catalog matches secret pattern {pattern.pattern!r}"
            )

    def test_no_live_looking_account_ids(self) -> None:
        text = _load_catalog_path().read_text(encoding="utf-8")
        for match in _ACCOUNT_ID_SHAPE.finditer(text):
            assert match.group() == DUMMY_ACCOUNT_ID, (
                f"seed catalog contains a non-dummy 12-digit account-id-shaped value: "
                f"{match.group()!r}"
            )

    def test_all_entries_declare_full_reuse_and_training_eligible_governance(self) -> None:
        raw = yaml.safe_load(_load_catalog_path().read_text(encoding="utf-8"))
        for entry in raw["entries"]:
            assert entry["license"] == "CC0-1.0"
            assert entry["reuse_status"] == "full_reuse"
            assert entry["allowed_for_training"] is True
