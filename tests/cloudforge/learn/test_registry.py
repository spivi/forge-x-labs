"""Source-registry loader tests: real file + governance + malformed-registry errors."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.cloudforge.learn.registry import (
    RegistryError,
    enabled_sources,
    get_entry,
    load_registry,
)
from app.cloudforge.learn.source_models import ReuseStatus

REAL_REGISTRY = Path("data/source_registry.yaml")


def test_load_real_registry_parses_without_error() -> None:
    registry = load_registry(REAL_REGISTRY)
    assert len(registry.sources) >= 4
    # every id is unique + resolvable.
    for entry in registry.sources:
        assert registry.by_id(entry.id) is entry


def test_csa_ccm_is_mappings_only_and_training_eligible() -> None:
    # FXL-D007: CSA CCM mappings_only stays training-eligible after governance.
    registry = load_registry(REAL_REGISTRY)
    csa = get_entry(registry, "csa-ccm")
    assert csa.reuse_status is ReuseStatus.MAPPINGS_ONLY
    assert csa.allowed_for_training is True


def test_checkov_is_metadata_only_and_not_training_eligible() -> None:
    registry = load_registry(REAL_REGISTRY)
    checkov = get_entry(registry, "checkov-terraform-index")
    assert checkov.reuse_status is ReuseStatus.METADATA_ONLY
    assert checkov.allowed_for_training is False


def test_cis_unknown_license_forced_not_training_eligible() -> None:
    registry = load_registry(REAL_REGISTRY)
    cis = get_entry(registry, "cis-benchmarks")
    assert cis.license == "unknown"
    assert cis.allowed_for_training is False


def test_local_rule_catalog_full_reuse_stays_training_eligible() -> None:
    registry = load_registry(REAL_REGISTRY)
    catalog = get_entry(registry, "local-rule-catalog")
    assert catalog.reuse_status is ReuseStatus.FULL_REUSE
    assert catalog.allowed_for_training is True


def test_enabled_sources_filters_disabled_entries() -> None:
    registry = load_registry(REAL_REGISTRY)
    enabled = enabled_sources(registry)
    enabled_ids = {e.id for e in enabled}
    assert "checkov-terraform-index" in enabled_ids
    assert "csa-ccm" not in enabled_ids  # enabled: false in the real file
    assert all(e.enabled for e in enabled)


# --- governance normalization (design §4) ------------------------------------


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "registry.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_governance_forces_false_when_license_unknown(tmp_path: Path) -> None:
    # declares allowed_for_training: true, but license unknown -> forced false.
    path = _write(
        tmp_path,
        """
sources:
  - id: sneaky
    name: sneaky
    type: iac_repo
    url: "https://example.com/x"
    adapter: rule_catalog_yaml
    enabled: true
    license: unknown
    reuse_status: full_reuse
    allowed_for_training: true
    notes: ""
""",
    )
    registry = load_registry(path)
    assert registry.by_id("sneaky").allowed_for_training is False  # type: ignore[union-attr]


def test_governance_forces_false_when_restricted(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        """
sources:
  - id: restricted-src
    name: restricted
    type: control_framework
    url: "https://example.com/x"
    adapter: rule_catalog_yaml
    enabled: true
    license: "Proprietary"
    reuse_status: restricted
    allowed_for_training: true
    notes: ""
""",
    )
    registry = load_registry(path)
    assert registry.by_id("restricted-src").allowed_for_training is False  # type: ignore[union-attr]


def test_governance_leaves_mappings_only_as_declared(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        """
sources:
  - id: ccm-like
    name: ccm-like
    type: control_framework
    url: "https://example.com/ccm"
    adapter: rule_catalog_yaml
    enabled: false
    license: "CSA CCM machine-readable"
    reuse_status: mappings_only
    allowed_for_training: true
    notes: ""
""",
    )
    registry = load_registry(path)
    assert registry.by_id("ccm-like").allowed_for_training is True  # type: ignore[union-attr]


# --- malformed-registry error cases ------------------------------------------


def test_missing_file_raises_registry_error(tmp_path: Path) -> None:
    with pytest.raises(RegistryError):
        load_registry(tmp_path / "does-not-exist.yaml")


def test_no_sources_key_raises_registry_error(tmp_path: Path) -> None:
    path = _write(tmp_path, "not_sources: []\n")
    with pytest.raises(RegistryError):
        load_registry(path)


def test_entry_with_both_url_and_path_raises(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        """
sources:
  - id: bad
    name: bad
    type: iac_repo
    url: "https://example.com/x"
    path: "local/x"
    adapter: rule_catalog_yaml
    enabled: true
    license: "MIT"
    reuse_status: full_reuse
    allowed_for_training: true
""",
    )
    with pytest.raises(RegistryError):
        load_registry(path)


def test_duplicate_ids_raise_registry_error(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        """
sources:
  - id: dupe
    name: a
    type: iac_repo
    url: "https://example.com/a"
    adapter: rule_catalog_yaml
    enabled: true
    license: "MIT"
    reuse_status: full_reuse
    allowed_for_training: true
  - id: dupe
    name: b
    type: iac_repo
    url: "https://example.com/b"
    adapter: rule_catalog_yaml
    enabled: true
    license: "MIT"
    reuse_status: full_reuse
    allowed_for_training: true
""",
    )
    with pytest.raises(RegistryError):
        load_registry(path)


def test_unknown_enum_value_raises_registry_error(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        """
sources:
  - id: badenum
    name: badenum
    type: not_a_real_type
    url: "https://example.com/x"
    adapter: rule_catalog_yaml
    enabled: true
    license: "MIT"
    reuse_status: full_reuse
    allowed_for_training: true
""",
    )
    with pytest.raises(RegistryError):
        load_registry(path)


def test_get_entry_unlisted_raises(tmp_path: Path) -> None:
    registry = load_registry(REAL_REGISTRY)
    with pytest.raises(RegistryError):
        get_entry(registry, "not-a-real-source")
