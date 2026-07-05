"""Registry-gated raw fetcher tests (design §4, issue #60).

All tests inject a fake ``fetch_bytes`` callable — there is NO real network access in
this suite. The one opt-in internet smoke test is marked ``internet`` and skipped by
default (see pytest.ini_options / ``-m 'not internet'`` posture); ticket #74 owns the
rest of that suite.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from app.cloudforge.learn.fetch import (
    MAX_RESPONSE_BYTES,
    USER_AGENT,
    FetchedResponse,
    FetchOutcome,
    fetch_all_sources,
)
from app.cloudforge.learn.source_models import ReuseStatus, SourceEntry, SourceType

_TS = "2026-07-05T12:00:00Z"


def _entry(
    *,
    source_id: str = "src-1",
    url: str | None = "https://example.com/a",
    path: str | None = None,
    enabled: bool = True,
) -> SourceEntry:
    return SourceEntry(
        id=source_id,
        name=f"{source_id} name",
        type=SourceType.SCANNER_RULE_INDEX,
        url=url,
        path=path,
        adapter="checkov_policy_index",
        enabled=enabled,
        license="Apache-2.0",
        reuse_status=ReuseStatus.METADATA_ONLY,
        allowed_for_training=False,
        notes="",
    )


def _ok_fetcher(body: bytes, *, content_type: str = "text/html", status: int = 200):
    def _fetch(url: str) -> FetchedResponse:
        return FetchedResponse(status_code=status, content_type=content_type, body=body)

    return _fetch


def _failing_fetcher(exc: Exception):
    def _fetch(url: str) -> FetchedResponse:
        raise exc

    return _fetch


class TestFetchOneSource:
    def test_writes_cache_bytes_and_metadata_with_correct_hash(self, tmp_path: Path) -> None:
        entry = _entry()
        body = b"<html>policy index</html>"
        summary = fetch_all_sources(sources=[entry], raw_dir=tmp_path, fetch_fn=_ok_fetcher(body))

        assert summary.fetched == 1
        assert summary.failed == 0
        assert summary.skipped == 0

        import hashlib

        expected_hash = hashlib.sha256(body).hexdigest()
        cache_path = tmp_path / entry.id / expected_hash
        metadata_path = tmp_path / entry.id / "metadata.json"

        assert cache_path.read_bytes() == body

        import json

        meta = json.loads(metadata_path.read_text(encoding="utf-8"))
        assert meta["source_id"] == entry.id
        assert meta["source_url_or_path"] == entry.url
        assert meta["content_hash"] == expected_hash
        assert meta["size_bytes"] == len(body)
        assert meta["http_status"] == 200
        assert meta["content_type"] == "text/html"
        assert meta["fetched_at"]

    def test_result_records_outcome_fetched(self, tmp_path: Path) -> None:
        entry = _entry()
        summary = fetch_all_sources(
            sources=[entry], raw_dir=tmp_path, fetch_fn=_ok_fetcher(b"data")
        )
        assert summary.results[0].source_id == entry.id
        assert summary.results[0].outcome is FetchOutcome.FETCHED


class TestFailSoft:
    def test_failing_source_is_recorded_and_run_continues(self, tmp_path: Path) -> None:
        bad = _entry(source_id="bad-src", url="https://example.com/bad")
        good = _entry(source_id="good-src", url="https://example.com/good")

        calls: list[str] = []

        def _fetch(url: str) -> FetchedResponse:
            calls.append(url)
            if "bad" in url:
                raise httpx.ConnectError("boom")
            return FetchedResponse(status_code=200, content_type="text/html", body=b"ok")

        summary = fetch_all_sources(sources=[bad, good], raw_dir=tmp_path, fetch_fn=_fetch)

        assert summary.failed == 1
        assert summary.fetched == 1
        assert len(calls) == 2  # the failure did not abort the run

        outcomes = {r.source_id: r.outcome for r in summary.results}
        assert outcomes["bad-src"] is FetchOutcome.FAILED
        assert outcomes["good-src"] is FetchOutcome.FETCHED

        # no cache written for the failed source
        assert not (tmp_path / "bad-src").exists()

    def test_http_status_error_is_fail_soft(self, tmp_path: Path) -> None:
        entry = _entry()
        response = httpx.Response(404, request=httpx.Request("GET", entry.url or ""))
        exc = httpx.HTTPStatusError("not found", request=response.request, response=response)
        summary = fetch_all_sources(
            sources=[entry], raw_dir=tmp_path, fetch_fn=_failing_fetcher(exc)
        )
        assert summary.failed == 1
        assert summary.results[0].outcome is FetchOutcome.FAILED
        assert summary.results[0].error is not None


class TestSkipping:
    def test_disabled_source_is_skipped_not_error(self, tmp_path: Path) -> None:
        entry = _entry(enabled=False)
        summary = fetch_all_sources(sources=[entry], raw_dir=tmp_path, fetch_fn=_ok_fetcher(b"x"))
        assert summary.skipped == 1
        assert summary.fetched == 0
        assert summary.failed == 0
        assert summary.results[0].outcome is FetchOutcome.SKIPPED_DISABLED

    def test_local_path_source_is_skipped_not_fetched(self, tmp_path: Path) -> None:
        entry = _entry(url=None, path="data/rule_catalog/seed_patterns.yaml")

        def _fetch(url: str) -> FetchedResponse:
            raise AssertionError("local sources must never be fetched over the network")

        summary = fetch_all_sources(sources=[entry], raw_dir=tmp_path, fetch_fn=_fetch)
        assert summary.skipped == 1
        assert summary.results[0].outcome is FetchOutcome.SKIPPED_LOCAL

    def test_disabled_takes_precedence_reported_once(self, tmp_path: Path) -> None:
        entry = _entry(enabled=False, url=None, path="local/x")
        summary = fetch_all_sources(sources=[entry], raw_dir=tmp_path, fetch_fn=None)
        assert summary.skipped == 1
        assert len(summary.results) == 1


class TestOversized:
    def test_oversized_response_is_refused_and_recorded_failed(self, tmp_path: Path) -> None:
        entry = _entry()
        oversized_body = b"x" * (MAX_RESPONSE_BYTES + 1)
        summary = fetch_all_sources(
            sources=[entry], raw_dir=tmp_path, fetch_fn=_ok_fetcher(oversized_body)
        )
        assert summary.failed == 1
        assert summary.fetched == 0
        assert summary.results[0].outcome is FetchOutcome.FAILED
        assert "max" in (summary.results[0].error or "").lower()
        assert not (tmp_path / entry.id).exists()

    def test_response_at_exact_limit_is_accepted(self, tmp_path: Path) -> None:
        entry = _entry()
        body = b"x" * MAX_RESPONSE_BYTES
        summary = fetch_all_sources(sources=[entry], raw_dir=tmp_path, fetch_fn=_ok_fetcher(body))
        assert summary.fetched == 1


class TestSummaryShape:
    def test_empty_source_list_returns_zeroed_summary(self, tmp_path: Path) -> None:
        summary = fetch_all_sources(sources=[], raw_dir=tmp_path, fetch_fn=None)
        assert summary.fetched == 0
        assert summary.skipped == 0
        assert summary.failed == 0
        assert summary.results == []

    def test_idempotent_refetch_overwrites_same_content_hash(self, tmp_path: Path) -> None:
        entry = _entry()
        body = b"same bytes"
        fetch_all_sources(sources=[entry], raw_dir=tmp_path, fetch_fn=_ok_fetcher(body))
        summary2 = fetch_all_sources(sources=[entry], raw_dir=tmp_path, fetch_fn=_ok_fetcher(body))
        assert summary2.fetched == 1

        import hashlib

        expected_hash = hashlib.sha256(body).hexdigest()
        assert (tmp_path / entry.id / expected_hash).read_bytes() == body


class TestDefaultHttpClient:
    def test_default_fetch_uses_user_agent_and_timeout(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The default (non-injected) HTTP path sends the module's UA + timeout.

        Uses ``monkeypatch`` on ``httpx.get`` rather than real network I/O.
        """
        captured: dict[str, object] = {}

        def _fake_get(url: str, *, headers: dict[str, str], timeout: float) -> httpx.Response:
            captured["url"] = url
            captured["headers"] = headers
            captured["timeout"] = timeout
            request = httpx.Request("GET", url)
            return httpx.Response(
                200, request=request, content=b"ok", headers={"content-type": "text/plain"}
            )

        monkeypatch.setattr(httpx, "get", _fake_get)

        from app.cloudforge.learn.fetch import default_fetch_bytes

        result = default_fetch_bytes("https://example.com/thing")

        assert result.status_code == 200
        assert result.body == b"ok"
        assert captured["headers"]["User-Agent"] == USER_AGENT
        assert captured["timeout"] > 0


@pytest.mark.internet
@pytest.mark.skip(reason="opt-in real-network smoke test; run explicitly with -m internet")
def test_real_network_fetch_smoke() -> None:
    """One trivial opt-in smoke test exercising the real default HTTP client.

    Skipped by default. Ticket #74 owns the full opt-in internet test suite; this is
    a single trivial marker-gated check that the default client wiring works end to end.
    """
    from app.cloudforge.learn.fetch import default_fetch_bytes

    result = default_fetch_bytes("https://www.checkov.io/5.Policy%20Index/terraform.html")
    assert result.status_code == 200
