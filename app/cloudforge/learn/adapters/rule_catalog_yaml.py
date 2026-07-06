"""``rule_catalog_yaml`` adapter — parses a LOCAL curated YAML rule catalog.

Reads a Tier-4 local rule catalog (design §8, adapter 2): a YAML file with a top-level
``entries:`` list, each describing a hand-authored defensive cloud-risk pattern. Emits
one ``RawPatternRecord`` per entry with complete provenance. Confidence default 0.75;
reuse/license/training-eligibility come from the ``SourceEntry`` (``local-rule-catalog``
is ``full_reuse`` / ``allowed_for_training: true``). This adapter does NOT normalize into
``RiskPattern`` (ticket #66) and never BUILDS a graph fragment itself — but a seed entry
may EMBED a hand-authored ``graph_fragment`` / ``expected_findings`` (ticket #98), which
are validated against the real product models and serialized into
``raw_payload["graph"]`` / ``raw_payload["expected_findings"]`` (``_embedded.py``) so
the normalizer reuses them verbatim.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from app.cloudforge.errors import CloudforgeError
from app.cloudforge.io.loaders import load_yaml
from app.cloudforge.learn.adapters._embedded import EMBEDDED_ENTRY_FIELDS, embedded_payload
from app.cloudforge.learn.pattern_models import CloudProvider, PatternProvenance, RawPatternRecord
from app.cloudforge.learn.source_models import SourceEntry
from app.cloudforge.models.findings import Severity

ADAPTER_NAME = "rule_catalog_yaml"
ADAPTER_VERSION = "0.1.0"
NORMALIZER_VERSION_UNSET = "unset"  # normalizer (ticket #66) stamps its own version later
_EXTRACTION_METHOD = "yaml_parse"
_DEFAULT_CONFIDENCE = 0.75


class RuleCatalogEntryError(CloudforgeError):
    """A rule catalog file is missing, unreadable, or one entry fails schema validation."""


class _RuleCatalogEntry(BaseModel):
    """Schema for one entry in a local rule catalog YAML file (design §8)."""

    model_config = ConfigDict(extra="allow")

    id: str
    title: str
    summary: str = ""
    cloud_provider: CloudProvider
    domains: list[str] = []
    weakness_family: str = ""
    severity: Severity
    affected_resource_types: list[str] = []
    remediation: str = ""
    references: list[str] = []


def _content_hash(raw_path: Path) -> str:
    try:
        return hashlib.sha256(raw_path.read_bytes()).hexdigest()
    except OSError as exc:
        raise RuleCatalogEntryError(f"cannot read rule catalog {raw_path}: {exc}") from exc


def _coerce_scalar(value: object) -> str:
    """Stringify a scalar catalog value so it fits ``RawPatternRecord.raw_payload``.

    ``raw_payload`` is typed ``dict[str, str | list[str]]`` (pattern_models.py, not
    modified here); catalog entries may carry bools/ints/None for a few fields
    (e.g. ``allowed_for_training: true``), so scalars are coerced to their YAML-ish
    string form rather than dropped.
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    return str(value)


def _coerce_raw_payload(raw_entry: dict[str, Any]) -> dict[str, str | list[str]]:
    """Narrow an arbitrary parsed catalog entry into ``raw_payload``'s declared shape.

    Embedded artifact fields (``graph_fragment``/``expected_findings``, ticket #98) are
    nested models, NOT flat scalars — running them through ``_coerce_scalar`` would
    ``str()``-mangle them into unparseable Python reprs, so they are excluded here and
    handled by ``embedded_payload`` (model-validated, JSON-encoded) instead.
    """
    payload: dict[str, str | list[str]] = {}
    for key, value in raw_entry.items():
        if key in EMBEDDED_ENTRY_FIELDS:
            continue
        if isinstance(value, list):
            payload[key] = [_coerce_scalar(item) for item in value]
        else:
            payload[key] = _coerce_scalar(value)
    return payload


def _load_catalog_entries(raw_path: Path) -> list[dict[str, Any]]:
    try:
        catalog = load_yaml(raw_path)
    except CloudforgeError as exc:
        raise RuleCatalogEntryError(f"cannot load rule catalog {raw_path}: {exc}") from exc

    entries = catalog.get("entries")
    if not isinstance(entries, list):
        raise RuleCatalogEntryError(
            f"rule catalog {raw_path} must have a top-level 'entries' list"
        )
    return entries


def _parse_entry(raw_entry: object, raw_path: Path) -> _RuleCatalogEntry:
    if not isinstance(raw_entry, dict):
        raise RuleCatalogEntryError(f"rule catalog {raw_path} has a non-mapping entry")
    try:
        return _RuleCatalogEntry.model_validate(raw_entry)
    except ValidationError as exc:
        entry_id = raw_entry.get("id", "<unknown>")
        raise RuleCatalogEntryError(
            f"rule catalog {raw_path} entry {entry_id!r} failed validation: {exc}"
        ) from exc


def _build_provenance(
    *, source: SourceEntry, content_hash: str, extracted_at: datetime
) -> PatternProvenance:
    return PatternProvenance(
        source_id=source.id,
        source_name=source.name,
        source_type=source.type,
        source_url_or_path=source.location,
        source_license=source.license,
        reuse_status=source.reuse_status,
        allowed_for_training=source.allowed_for_training,
        extraction_method=_EXTRACTION_METHOD,
        fetched_at=extracted_at,
        extracted_at=extracted_at,
        content_hash=content_hash,
        adapter_name=ADAPTER_NAME,
        adapter_version=ADAPTER_VERSION,
        normalizer_version=NORMALIZER_VERSION_UNSET,
        confidence=_DEFAULT_CONFIDENCE,
        notes="parsed from local curated YAML rule catalog",
    )


def _to_record(
    entry: _RuleCatalogEntry, raw_entry: dict[str, Any], provenance: PatternProvenance
) -> RawPatternRecord:
    raw_payload = _coerce_raw_payload(raw_entry)
    raw_payload.update(embedded_payload(raw_entry, entry.id))
    return RawPatternRecord(
        source_id=provenance.source_id,
        raw_id=entry.id,
        title=entry.title,
        summary=entry.summary,
        cloud_provider=entry.cloud_provider,
        resource_types=list(entry.affected_resource_types),
        severity=entry.severity,
        category=entry.domains[0] if entry.domains else None,
        remediation=entry.remediation,
        references=list(entry.references),
        raw_payload=raw_payload,
        provenance=provenance,
    )


class RuleCatalogYamlAdapter:
    """Parses a local curated YAML rule catalog into ``RawPatternRecord``s (design §8)."""

    adapter_name = ADAPTER_NAME
    adapter_version = ADAPTER_VERSION

    def extract(
        self,
        source: SourceEntry,
        raw_path: Path,
        *,
        extracted_at: datetime | None = None,
    ) -> list[RawPatternRecord]:
        """Parse ``raw_path`` (a rule catalog YAML file) into ``RawPatternRecord``s.

        Raises ``RuleCatalogEntryError`` (a ``CloudforgeError``) on a missing file,
        malformed YAML, or an entry that fails schema validation — never crashes with a
        bare parser/attribute exception.
        """
        stamp = extracted_at if extracted_at is not None else datetime.now(UTC)
        content_hash = _content_hash(raw_path)
        raw_entries = _load_catalog_entries(raw_path)

        provenance = _build_provenance(
            source=source, content_hash=content_hash, extracted_at=stamp
        )
        records: list[RawPatternRecord] = []
        for raw_entry in raw_entries:
            entry = _parse_entry(raw_entry, raw_path)
            records.append(_to_record(entry, raw_entry, provenance))
        return records
