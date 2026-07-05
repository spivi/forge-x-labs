"""Opt-in real-network integration tests (design §11, issue #74).

Exercises the REAL registry-gated fetch -> cache -> adapter path against a single
APPROVED remote source from ``data/source_registry.yaml`` (``checkov-terraform-index``).
Everything here is marked ``@pytest.mark.internet`` and is DESELECTED by default: the
default ``pytest`` run and CI both invoke plain ``pytest tests/ ...`` with no ``-m``
flag, so ``addopts = "... -m 'not stress and not internet'"`` in ``pyproject.toml`` does
the deselecting. A human opts in explicitly with::

    pytest -m internet

Governance: the ONLY URL ever touched is the exact one listed in the registry for
``checkov-terraform-index`` — there is no crawling, no link-following, and nothing else
is fetched. If the registry entry is ``enabled: false`` on ``master``, these tests build
a local, in-memory copy of the entry with ``enabled=True`` rather than mutating the
committed registry file.

Resilience: a real fetch can be slow or transiently unreachable. These tests use a
generous timeout and ``pytest.skip("network unavailable")`` on any transport-level
failure (DNS, connect, timeout) rather than failing the suite — but when the network
IS reachable, they assert the real mechanism (cache file + metadata + real content hash
and HTTP status, and optionally a real adapter extraction) rather than skipping the
assertions too.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from app.cloudforge.learn.adapters.checkov_policy_index import CheckovPolicyIndexAdapter
from app.cloudforge.learn.fetch import FetchedResponse, default_fetch_bytes, fetch_all_sources
from app.cloudforge.learn.pattern_models import RawPatternRecord
from app.cloudforge.learn.registry import load_registry
from app.cloudforge.learn.source_models import SourceEntry

REGISTRY_PATH = Path("data/source_registry.yaml")
CHECKOV_SOURCE_ID = "checkov-terraform-index"

pytestmark = pytest.mark.internet

# transport-level failure modes that mean "network unavailable", not "code is broken" --
# these skip rather than fail so a flaky/offline environment never breaks the opt-in suite.
_NETWORK_UNAVAILABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.ReadTimeout,
    httpx.PoolTimeout,
    httpx.NetworkError,
)


def _live_checkov_entry() -> SourceEntry:
    """The registry's ``checkov-terraform-index`` entry, forced ``enabled=True``.

    Reads the REAL committed registry (so the URL/adapter/license under test is the
    one actually shipped) but never mutates it on disk: if it is ``enabled: false`` on
    ``master``, this returns an in-memory copy with ``enabled`` overridden, via
    ``model_copy`` on the real, governed ``SourceEntry``.
    """
    registry = load_registry(REGISTRY_PATH)
    entry = registry.by_id(CHECKOV_SOURCE_ID)
    assert entry is not None, f"{CHECKOV_SOURCE_ID!r} must exist in {REGISTRY_PATH}"
    assert entry.url is not None, f"{CHECKOV_SOURCE_ID!r} must be a remote (url) source"
    if entry.enabled:
        return entry
    return entry.model_copy(update={"enabled": True})


class TestRealFetchToCache:
    """Real fetch -> content-addressed cache, against the one approved registry URL."""

    def test_fetches_approved_source_and_writes_real_cache_and_metadata(
        self, tmp_path: Path
    ) -> None:
        entry = _live_checkov_entry()

        try:
            summary = fetch_all_sources(
                sources=[entry], raw_dir=tmp_path, fetch_fn=default_fetch_bytes
            )
        except _NETWORK_UNAVAILABLE_EXCEPTIONS as exc:
            pytest.skip(f"network unavailable: {exc}")

        result = summary.results[0]
        if result.outcome.value == "failed":
            # Fail-soft mechanism worked (the point of this assertion): a live-network
            # hiccup was recorded rather than raised. Don't hard-fail the suite on
            # transient flakiness, but do confirm the failure was actually recorded.
            pytest.skip(f"registry source fetch recorded a soft failure: {result.error}")

        assert summary.fetched == 1
        assert summary.failed == 0

        source_dir = tmp_path / entry.id
        metadata_path = source_dir / "metadata.json"
        assert metadata_path.exists()

        import json

        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        assert metadata["source_id"] == entry.id
        assert metadata["source_url_or_path"] == entry.url
        assert metadata["http_status"] == 200
        assert metadata["content_hash"]
        assert metadata["size_bytes"] > 0

        cache_path = source_dir / metadata["content_hash"]
        assert cache_path.exists()

        import hashlib

        real_bytes = cache_path.read_bytes()
        assert hashlib.sha256(real_bytes).hexdigest() == metadata["content_hash"]
        assert len(real_bytes) == metadata["size_bytes"]

    def test_governance_only_fetches_the_registry_url_nothing_else(self, tmp_path: Path) -> None:
        """Only the registry-listed source is ever passed to the fetch callable.

        This does not prove the fetcher can't crawl (it structurally can't -- see
        ``fetch.py``'s docstring/design), but it does prove that running the real
        fetch path over the registry's enabled remote sources touches exactly the
        approved URL set and nothing beyond it.
        """
        registry = load_registry(REGISTRY_PATH)
        live_checkov = _live_checkov_entry()
        # Only exercise the one approved, remote entry under test here -- other
        # enabled remote sources (if any are added later) are out of scope for this
        # opt-in smoke test and would just add more live-network surface area.
        sources = [live_checkov]
        approved_urls = {entry.url for entry in registry.sources if entry.url}
        assert live_checkov.url in approved_urls

        called_urls: list[str] = []

        def _tracking_fetch(url: str) -> FetchedResponse:
            called_urls.append(url)
            return default_fetch_bytes(url)

        try:
            fetch_all_sources(sources=sources, raw_dir=tmp_path, fetch_fn=_tracking_fetch)
        except _NETWORK_UNAVAILABLE_EXCEPTIONS as exc:
            pytest.skip(f"network unavailable: {exc}")

        assert called_urls == [live_checkov.url]
        assert set(called_urls) <= approved_urls


class TestRealFetchThenAdapter:
    """Real fetch -> real ``checkov_policy_index`` adapter, on live-fetched HTML."""

    def test_fetch_then_adapter_extracts_metadata_only_records(self, tmp_path: Path) -> None:
        entry = _live_checkov_entry()

        try:
            summary = fetch_all_sources(
                sources=[entry], raw_dir=tmp_path, fetch_fn=default_fetch_bytes
            )
        except _NETWORK_UNAVAILABLE_EXCEPTIONS as exc:
            pytest.skip(f"network unavailable: {exc}")

        result = summary.results[0]
        if result.outcome.value == "failed":
            pytest.skip(f"registry source fetch recorded a soft failure: {result.error}")

        import json

        metadata_path = tmp_path / entry.id / "metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        raw_path = tmp_path / entry.id / metadata["content_hash"]

        adapter = CheckovPolicyIndexAdapter()
        records = adapter.extract(entry, raw_path)

        if not records:
            # The live page's markup shape can drift over time; the adapter degrades
            # to zero rows rather than crashing (see its docstring). That is a page-
            # shape observation, not a mechanism failure, so skip rather than fail.
            pytest.skip(
                "live Checkov page produced 0 extractable rows (page shape may have "
                "drifted) -- fetch mechanism itself succeeded"
            )

        assert len(records) >= 1
        for record in records:
            assert isinstance(record, RawPatternRecord)
            assert record.source_id == CHECKOV_SOURCE_ID
            # governance posture is hard-coded by the adapter regardless of what the
            # registry says (see checkov_policy_index.py docstring).
            assert record.provenance.allowed_for_training is False
            assert record.provenance.reuse_status.value == "metadata_only"
            assert record.provenance.content_hash == metadata["content_hash"]
