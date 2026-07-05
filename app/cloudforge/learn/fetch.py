"""Registry-gated raw fetcher (design §4, issue #60).

Fetches every ``enabled`` registry source that has a remote ``url`` into a
content-addressed cache at ``data/raw/<source_id>/<content_hash>`` plus a
``metadata.json`` sidecar (``RawCacheMetadata``). Registry-gated: the ONLY URLs ever
touched are the exact ones listed in ``data/source_registry.yaml`` — there is NO
crawling, NO link-following, and NO search/GitHub scraping. Local-``path`` sources and
``enabled: false`` sources are skipped, not errors. Each source fetch is fail-soft: one
source's failure is recorded and the run continues.

See design §2 (pipeline) and §4 (raw-cache layout, governance rules).
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

import httpx
from pydantic import BaseModel, ConfigDict

from app.cloudforge.errors import CloudforgeError
from app.cloudforge.io.loaders import dump_json
from app.cloudforge.learn.source_models import RawCacheMetadata, SourceEntry

logger = logging.getLogger(__name__)

#: identifies cloudforge to remote hosts; never impersonate a browser.
USER_AGENT = "cloudforge-learn-fetcher/0.1 (+https://github.com/spivi/forge-x-labs)"
#: per-request network timeout (seconds).
TIMEOUT_SECONDS = 30.0
#: hard cap on a single response body; oversized responses are refused, not truncated,
#: so a cached fragment never silently masquerades as the complete source.
MAX_RESPONSE_BYTES = 10 * 1024 * 1024  # 10 MiB

_METADATA_FILENAME = "metadata.json"


class FetchError(CloudforgeError):
    """A hard fetcher-configuration error (not a per-source network failure)."""


class FetchOutcome(StrEnum):
    """What happened to one registry source during a fetch run."""

    FETCHED = "fetched"
    SKIPPED_DISABLED = "skipped_disabled"
    SKIPPED_LOCAL = "skipped_local"
    FAILED = "failed"


class FetchedResponse(BaseModel):
    """The bytes and metadata a ``fetch_fn`` returns for one URL."""

    model_config = ConfigDict(extra="forbid")

    status_code: int
    content_type: str | None
    body: bytes


class SourceFetchResult(BaseModel):
    """The per-source outcome of one fetch run."""

    model_config = ConfigDict(extra="forbid")

    source_id: str
    outcome: FetchOutcome
    error: str | None = None


class FetchSummary(BaseModel):
    """Aggregate counts plus the full per-source result list."""

    model_config = ConfigDict(extra="forbid")

    fetched: int = 0
    skipped: int = 0
    failed: int = 0
    results: list[SourceFetchResult] = []


#: injectable fetch callable so tests never touch the network; the default
#: implementation (``default_fetch_bytes``) is the only real-network path.
FetchFn = Callable[[str], FetchedResponse]


def default_fetch_bytes(url: str) -> FetchedResponse:
    """Fetch ``url`` with the module's User-Agent and timeout (the real network path).

    Raises ``httpx.HTTPError`` on any transport/status failure; callers must catch it.
    """
    response = httpx.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    return FetchedResponse(
        status_code=response.status_code,
        content_type=response.headers.get("content-type"),
        body=response.content,
    )


def fetch_all_sources(
    *,
    sources: list[SourceEntry],
    raw_dir: Path,
    fetch_fn: FetchFn | None,
) -> FetchSummary:
    """Fetch every enabled, remote (``url``-having) entry in ``sources``.

    Local-``path`` and ``enabled: false`` entries are skipped, not errors. Each
    source's fetch is fail-soft — a failure is recorded in the summary and the run
    continues. ``fetch_fn`` defaults to ``default_fetch_bytes`` (real network); tests
    inject a fake to avoid any network access.
    """
    fetch = fetch_fn or default_fetch_bytes
    results = [_fetch_one(entry, raw_dir, fetch) for entry in sources]
    return _summarize(results)


def _fetch_one(entry: SourceEntry, raw_dir: Path, fetch: FetchFn) -> SourceFetchResult:
    """Fetch one source, returning its outcome (never raises)."""
    if not entry.enabled:
        logger.info("skip disabled source", extra={"source_id": entry.id})
        return SourceFetchResult(source_id=entry.id, outcome=FetchOutcome.SKIPPED_DISABLED)
    if entry.url is None:
        logger.info("skip local-path source", extra={"source_id": entry.id})
        return SourceFetchResult(source_id=entry.id, outcome=FetchOutcome.SKIPPED_LOCAL)

    try:
        response = fetch(entry.url)
        _check_size(response.body)
        _write_cache(raw_dir, entry, response)
    except (httpx.HTTPError, FetchError) as exc:
        logger.warning("fetch failed", extra={"source_id": entry.id, "error": str(exc)})
        return SourceFetchResult(source_id=entry.id, outcome=FetchOutcome.FAILED, error=str(exc))

    logger.info("fetched source", extra={"source_id": entry.id})
    return SourceFetchResult(source_id=entry.id, outcome=FetchOutcome.FETCHED)


def _check_size(body: bytes) -> None:
    """Refuse (fail-soft, via ``FetchError``) any response over ``MAX_RESPONSE_BYTES``."""
    if len(body) > MAX_RESPONSE_BYTES:
        raise FetchError(
            f"response of {len(body)} bytes exceeds max allowed {MAX_RESPONSE_BYTES} bytes"
        )


def _write_cache(raw_dir: Path, entry: SourceEntry, response: FetchedResponse) -> None:
    """Write the content-addressed bytes + ``metadata.json`` sidecar for ``entry``."""
    content_hash = hashlib.sha256(response.body).hexdigest()
    source_dir = raw_dir / entry.id
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / content_hash).write_bytes(response.body)

    metadata = RawCacheMetadata(
        source_id=entry.id,
        source_url_or_path=entry.url or "",
        fetched_at=datetime.now(UTC).isoformat(),
        http_status=response.status_code,
        content_type=response.content_type,
        content_hash=content_hash,
        size_bytes=len(response.body),
    )
    dump_json(source_dir / _METADATA_FILENAME, metadata.model_dump())


def _summarize(results: list[SourceFetchResult]) -> FetchSummary:
    """Aggregate per-source results into a ``FetchSummary``."""
    summary = FetchSummary(results=results)
    for result in results:
        if result.outcome is FetchOutcome.FETCHED:
            summary.fetched += 1
        elif result.outcome is FetchOutcome.FAILED:
            summary.failed += 1
        else:
            summary.skipped += 1
    return summary
