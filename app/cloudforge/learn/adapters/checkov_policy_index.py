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
yields fewer (or zero) rows rather than raising, mirroring how a browser degrades. A
missing/unreadable fixture file *is* a hard error (``CheckovParseError``) since that is
an operator mistake, not a page-shape variation.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path

from app.cloudforge.errors import CloudforgeError
from app.cloudforge.learn.pattern_models import CloudProvider, PatternProvenance, RawPatternRecord
from app.cloudforge.learn.source_models import ReuseStatus, SourceEntry
from app.cloudforge.models.findings import Severity

ADAPTER_NAME = "checkov_policy_index"
ADAPTER_VERSION = "1.0.0"
EXTRACTION_METHOD = "fixture_html_metadata"
CONFIDENCE_DEFAULT = 0.55

# fixture table column order: check_id, kind, resource_type, title, iac_type, severity
_CLOUD_PREFIXES: tuple[tuple[str, CloudProvider], ...] = (
    ("CKV_AWS_", CloudProvider.AWS),
    ("CKV_AZURE_", CloudProvider.AZURE),
    ("CKV_GCP_", CloudProvider.GCP),
    ("CKV_K8S_", CloudProvider.KUBERNETES),
)
_KNOWN_SEVERITIES: frozenset[str] = frozenset({"low", "medium", "high", "critical"})


class CheckovParseError(CloudforgeError):
    """The fixture HTML could not be read (missing file, unreadable, undecodable)."""


class _PolicyTableParser(HTMLParser):
    """Collects one cell-text list per ``<tr>`` inside a ``<table>``.

    Deliberately minimal and tolerant: unknown/unclosed tags are ignored rather than
    raising, so a malformed fixture degrades to fewer/zero rows instead of crashing.
    """

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._in_table = False
        self._in_row = False
        self._in_cell = False
        self._current_row: list[str] = []
        self._current_cell: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self._in_table = True
        elif tag == "tr" and self._in_table:
            self._in_row = True
            self._current_row = []
        elif tag in ("td", "th") and self._in_row:
            self._in_cell = True
            self._current_cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self._in_cell:
            self._current_row.append("".join(self._current_cell).strip())
            self._in_cell = False
        elif tag == "tr" and self._in_row:
            if self._current_row:
                self.rows.append(self._current_row)
            self._in_row = False
        elif tag == "table":
            self._in_table = False

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._current_cell.append(data)


def _cloud_provider_for(check_id: str) -> CloudProvider:
    """Map a Checkov check id prefix (e.g. ``CKV_AWS_20``) to a ``CloudProvider``."""
    for prefix, provider in _CLOUD_PREFIXES:
        if check_id.startswith(prefix):
            return provider
    return CloudProvider.GENERIC


def _severity_for(raw: str) -> Severity | None:
    """Normalize a free-text severity cell to the shared ``Severity`` literal, if known."""
    lowered = raw.strip().lower()
    return lowered if lowered in _KNOWN_SEVERITIES else None  # type: ignore[return-value]


def _read_fixture_bytes(raw_path: Path) -> bytes:
    try:
        return raw_path.read_bytes()
    except OSError as exc:
        raise CheckovParseError(f"cannot read Checkov fixture {raw_path}: {exc}") from exc


def _parse_rows(html_text: str) -> list[list[str]]:
    parser = _PolicyTableParser()
    parser.feed(html_text)
    parser.close()
    # header row (or any row missing a recognizable check id in column 0) is dropped.
    return [row for row in parser.rows if len(row) >= 3 and row[0].strip().startswith("CKV")]


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
