"""``_ingest.py`` helper tests: adapter resolution + cached raw-path lookup."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.cloudforge.learn._ingest import (
    NoCachedRawSourceError,
    UnknownAdapterError,
    resolve_adapter,
    resolve_raw_path,
)
from app.cloudforge.learn.adapters.rule_catalog_yaml import RuleCatalogYamlAdapter
from app.cloudforge.learn.source_models import ReuseStatus, SourceEntry, SourceType


def _remote_entry(source_id: str = "remote-src") -> SourceEntry:
    return SourceEntry(
        id=source_id,
        name="remote source",
        type=SourceType.SCANNER_RULE_INDEX,
        url="https://example.com/thing",
        adapter="checkov_policy_index",
        enabled=True,
        license="Apache-2.0",
        reuse_status=ReuseStatus.METADATA_ONLY,
        allowed_for_training=False,
    )


def _local_entry(path: str = "data/rule_catalog/seed_patterns.yaml") -> SourceEntry:
    return SourceEntry(
        id="local-src",
        name="local source",
        type=SourceType.LOCAL_RULE_CATALOG,
        path=path,
        adapter="rule_catalog_yaml",
        enabled=True,
        license="CC0-1.0",
        reuse_status=ReuseStatus.FULL_REUSE,
        allowed_for_training=True,
    )


class TestResolveAdapter:
    def test_resolves_known_adapter_by_name(self) -> None:
        adapter = resolve_adapter("rule_catalog_yaml")

        assert isinstance(adapter, RuleCatalogYamlAdapter)

    def test_unknown_adapter_raises_clean_error_listing_known_names(self) -> None:
        with pytest.raises(UnknownAdapterError) as exc_info:
            resolve_adapter("totally_made_up")

        message = str(exc_info.value)
        assert "totally_made_up" in message
        assert "rule_catalog_yaml" in message


class TestResolveRawPath:
    def test_local_source_resolves_its_declared_path_inside_the_project_root(self) -> None:
        # resolve_raw_path now returns a CONTAINED, resolved absolute path (path-traversal
        # guard): the returned path is inside the project root (CWD) and points at
        # the declared in-tree file. It is no longer the bare relative path.
        entry = _local_entry()

        resolved = resolve_raw_path(entry, Path("data/raw"))

        base = Path.cwd().resolve()
        assert resolved.is_absolute()
        assert resolved.is_relative_to(base)
        assert resolved == (base / "data/rule_catalog/seed_patterns.yaml").resolve()

    def test_remote_source_returns_the_latest_cached_file(self, tmp_path: Path) -> None:
        entry = _remote_entry()
        source_dir = tmp_path / entry.id
        source_dir.mkdir()
        (source_dir / "metadata.json").write_text("{}", encoding="utf-8")
        older = source_dir / "aaa_hash"
        newer = source_dir / "bbb_hash"
        older.write_bytes(b"old")
        newer.write_bytes(b"new")

        import os
        import time

        # ensure a strictly later mtime on the "newer" file regardless of fs mtime granularity.
        now = time.time()
        os.utime(older, (now - 10, now - 10))
        os.utime(newer, (now, now))

        resolved = resolve_raw_path(entry, tmp_path)

        assert resolved == newer

    def test_remote_source_with_no_cache_raises_clean_error(self, tmp_path: Path) -> None:
        entry = _remote_entry()

        with pytest.raises(NoCachedRawSourceError) as exc_info:
            resolve_raw_path(entry, tmp_path)

        assert entry.id in str(exc_info.value)
        assert "fetch-sources" in str(exc_info.value)

    def test_remote_source_ignores_metadata_json_as_a_candidate(self, tmp_path: Path) -> None:
        entry = _remote_entry()
        source_dir = tmp_path / entry.id
        source_dir.mkdir()
        (source_dir / "metadata.json").write_text("{}", encoding="utf-8")

        with pytest.raises(NoCachedRawSourceError):
            resolve_raw_path(entry, tmp_path)
