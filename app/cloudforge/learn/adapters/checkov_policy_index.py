"""``checkov_policy_index`` adapter — METADATA-ONLY, from a recorded fixture HTML.

Extracts policy IDs, resource types, titles, IaC type, and severity from a **recorded
fixture** HTML of the Checkov Terraform policy index. This adapter never fetches the
live Checkov site (that is the registry-gated fetcher's job) and never copies rule
source or rule logic into a record — only the same short metadata a human browsing the
public index page would see. ``reuse_status`` is always ``metadata_only`` and
``allowed_for_training`` is always ``False`` regardless of what the registry entry says,
matching the governance posture in design §3 (Tier 1) / §8.

Parsing uses the stdlib ``html.parser.HTMLParser`` (no BeautifulSoup dependency): a
small table-row collector that is tolerant of malformed/unclosed markup and simply
yields fewer (or zero) rows rather than raising, mirroring how a browser degrades. The
check-id column is located by content (see ``_parse_rows``), not a fixed position, so
both the fixture's shape and the live page's extra leading index column parse the same
way (issue #90). A missing/unreadable fixture file *is* a hard error
(``CheckovParseError``) since that is an operator mistake, not a page-shape variation.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.cloudforge.errors import CloudforgeError
from app.cloudforge.learn.adapters._html_table_parser import PolicyTableParser
from app.cloudforge.learn.pattern_models import CloudProvider, PatternProvenance, RawPatternRecord
from app.cloudforge.learn.source_models import ReuseStatus, SourceEntry
from app.cloudforge.models.findings import Severity

ADAPTER_NAME = "checkov_policy_index"
ADAPTER_VERSION = "1.0.0"
EXTRACTION_METHOD = "fixture_html_metadata"
CONFIDENCE_DEFAULT = 0.55

# Checkov's check-id pattern, used to locate the check-id column BY CONTENT rather than
# a fixed position (issue #90). Covers both plain checks (``CKV_AWS_20``, ``CKV_K8S_8``)
# and graph checks (``CKV2_AWS_5``, ``CKV2_AZURE_1``) — the ``\d*`` after ``CKV`` matches
# the ``2`` in the graph-check form, which live terraform index pages do include.
_CHECK_ID_PATTERN = re.compile(r"CKV\d*_[A-Z0-9]+_\d+")

# Captures the provider token (``AWS``/``AZURE``/…) after either ``CKV_`` or ``CKV2_``,
# so graph checks (``CKV2_AWS_5``) classify the same as plain checks (``CKV_AWS_5``).
_PROVIDER_TOKEN_PATTERN = re.compile(r"CKV\d*_([A-Z0-9]+)_")

# table column order (relative to the detected check-id column): check_id, kind,
# resource_type, title, iac_type, severity
_CLOUD_PROVIDER_BY_TOKEN: dict[str, CloudProvider] = {
    "AWS": CloudProvider.AWS,
    "AZURE": CloudProvider.AZURE,
    "GCP": CloudProvider.GCP,
    "K8S": CloudProvider.KUBERNETES,
}
_KNOWN_SEVERITIES: frozenset[str] = frozenset({"low", "medium", "high", "critical"})


class CheckovParseError(CloudforgeError):
    """The fixture HTML could not be read (missing file, unreadable, undecodable)."""


def _cloud_provider_for(check_id: str) -> CloudProvider:
    """Map a Checkov check id to a ``CloudProvider`` by its provider token.

    Tolerates both plain (``CKV_AWS_20``) and graph (``CKV2_AWS_5``) forms — the
    provider token (``AWS``) is the same in each; only the ``CKV``/``CKV2`` prefix
    differs. Unknown/absent tokens fall back to ``GENERIC``.
    """
    match = _PROVIDER_TOKEN_PATTERN.match(check_id)
    if match is None:
        return CloudProvider.GENERIC
    return _CLOUD_PROVIDER_BY_TOKEN.get(match.group(1), CloudProvider.GENERIC)


def _severity_for(raw: str) -> Severity | None:
    """Normalize a free-text severity cell to the shared ``Severity`` literal, if known."""
    lowered = raw.strip().lower()
    return lowered if lowered in _KNOWN_SEVERITIES else None  # type: ignore[return-value]


def _read_fixture_bytes(raw_path: Path) -> bytes:
    try:
        return raw_path.read_bytes()
    except OSError as exc:
        raise CheckovParseError(f"cannot read Checkov fixture {raw_path}: {exc}") from exc


def _check_id_column(row: list[str]) -> int | None:
    """Index of the cell matching the check-id pattern, or ``None`` (content, not position)."""
    for index, cell in enumerate(row):
        if _CHECK_ID_PATTERN.fullmatch(cell.strip()):
            return index
    return None


def _parse_rows(html_text: str) -> list[list[str]]:
    """Collect table rows, normalized so ``row[0]`` is always the check-id cell.

    Handles both the no-leading-column fixture shape and the live page's leading
    row-index column (issue #90) by locating the id cell per row instead of assuming a
    fixed position. A row with no recognizable id cell is skipped, not raised — the
    existing fail-soft posture is preserved.
    """
    parser = PolicyTableParser()
    parser.feed(html_text)
    parser.close()

    normalized: list[list[str]] = []
    for row in parser.rows:
        id_index = _check_id_column(row)
        if id_index is None:
            continue
        trimmed = row[id_index:]
        if len(trimmed) >= 3:
            normalized.append(trimmed)
    return normalized


def _cell(row: list[str], index: int) -> str:
    """Return ``row[index]`` or ``""`` if the fixture row is short that column."""
    return row[index] if len(row) > index else ""


@dataclass(frozen=True, slots=True)
class _ExtractionContext:
    """Bundles the per-``extract()``-call values shared by every emitted record."""

    source: SourceEntry
    content_hash: str
    extracted_at: datetime


class CheckovPolicyIndexAdapter:
    """``PatternAdapter`` for the recorded Checkov Terraform policy-index fixture."""

    adapter_name: str = ADAPTER_NAME
    adapter_version: str = ADAPTER_VERSION

    def extract(self, source: SourceEntry, raw_path: Path) -> list[RawPatternRecord]:
        """Parse the fixture HTML at ``raw_path`` into metadata-only records.

        Returns an empty list if no policy rows are found (e.g. an empty/placeholder
        page). Raises ``CheckovParseError`` if the fixture file itself cannot be read.
        """
        raw_bytes = _read_fixture_bytes(raw_path)
        html_text = raw_bytes.decode("utf-8", errors="replace")
        context = _ExtractionContext(
            source=source,
            content_hash=hashlib.sha256(raw_bytes).hexdigest(),
            extracted_at=datetime.now(UTC),
        )

        return [self._build_record(row, context) for row in _parse_rows(html_text)]

    def _build_record(self, row: list[str], context: _ExtractionContext) -> RawPatternRecord:
        check_id = row[0]
        resource_type = _cell(row, 2)
        title = _cell(row, 3)
        severity = _severity_for(_cell(row, 5)) if len(row) > 5 else None

        return RawPatternRecord(
            source_id=context.source.id,
            raw_id=check_id,
            title=title or check_id,
            summary="",
            cloud_provider=_cloud_provider_for(check_id),
            resource_types=[resource_type] if resource_type else [],
            rule_id=check_id,
            severity=severity,
            category=None,
            remediation="",
            references=[f"{context.source.location}#{check_id}"],
            raw_payload={},
            provenance=self._build_provenance(check_id, context),
        )

    def _build_provenance(self, check_id: str, context: _ExtractionContext) -> PatternProvenance:
        source = context.source
        return PatternProvenance(
            source_id=source.id,
            source_name=source.name,
            source_type=source.type,
            source_url_or_path=source.location,
            source_license=source.license,
            reuse_status=ReuseStatus.METADATA_ONLY,
            allowed_for_training=False,
            extraction_method=EXTRACTION_METHOD,
            fetched_at=context.extracted_at,
            extracted_at=context.extracted_at,
            content_hash=context.content_hash,
            adapter_name=self.adapter_name,
            adapter_version=self.adapter_version,
            normalizer_version="unnormalized",
            confidence=CONFIDENCE_DEFAULT,
            notes=f"metadata only; rule source/logic not copied ({check_id})",
        )
