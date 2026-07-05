"""Source-model tests: SourceEntry location, RawCacheMetadata round-trip, adapter protocol."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.cloudforge.learn.adapters.base import PatternAdapter
from app.cloudforge.learn.pattern_models import RawPatternRecord
from app.cloudforge.learn.source_models import (
    RawCacheMetadata,
    SourceEntry,
    SourceType,
)

from .conftest import build_provenance


def _entry(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": "x",
        "name": "x",
        "type": "iac_repo",
        "url": "https://example.com/x",
        "adapter": "rule_catalog_yaml",
        "enabled": True,
        "license": "MIT",
        "reuse_status": "full_reuse",
        "allowed_for_training": True,
    }
    base.update(overrides)
    return base


def test_source_entry_location_returns_url_or_path() -> None:
    url_entry = SourceEntry.model_validate(_entry())
    assert url_entry.location == "https://example.com/x"

    path_entry = SourceEntry.model_validate(
        _entry(url=None, path="data/x", type="local_rule_catalog")
    )
    assert path_entry.location == "data/x"
    assert path_entry.type is SourceType.LOCAL_RULE_CATALOG


def test_source_entry_neither_url_nor_path_raises() -> None:
    with pytest.raises(ValidationError):
        SourceEntry.model_validate(_entry(url=None, path=None))


def test_raw_cache_metadata_round_trips() -> None:
    meta = RawCacheMetadata(
        source_id="checkov-terraform-index",
        source_url_or_path="https://www.checkov.io/x.html",
        fetched_at="2026-07-05T12:00:00Z",
        http_status=200,
        content_type="text/html",
        content_hash="cafebabe",
        size_bytes=4096,
    )
    assert RawCacheMetadata.model_validate(meta.model_dump()) == meta


class _FakeAdapter:
    adapter_name = "fake"
    adapter_version = "0.0.1"

    def extract(self, source: SourceEntry, raw_path: Path) -> list[RawPatternRecord]:
        return [
            RawPatternRecord(
                source_id=source.id,
                raw_id="r-1",
                title="t",
                provenance=build_provenance(),
            )
        ]


def test_pattern_adapter_protocol_is_structural() -> None:
    adapter = _FakeAdapter()
    assert isinstance(adapter, PatternAdapter)
    records = adapter.extract(SourceEntry.model_validate(_entry()), Path("."))
    assert records[0].raw_id == "r-1"
