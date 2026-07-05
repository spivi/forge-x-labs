"""Source-registry models — the allow-list the fetcher/ingester is bound to.

The registry (``data/source_registry.yaml``) is the ONLY set of sources the corpus is
permitted to touch; the fetcher refuses anything not listed (or ``enabled: false``).
Each entry's fields are stamped into ``PatternProvenance`` on the patterns it produces.

Governance (per design §4, applied by ``registry.load_registry``): ``license: unknown``
and ``reuse_status`` in {restricted, metadata_only} force ``allowed_for_training=false``;
``mappings_only`` stays as-declared (FXL-D007 — CCM control-ID mappings are eligible).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, model_validator


class SourceType(StrEnum):
    """The kind of source an entry describes (design §4)."""

    SCANNER_RULE_INDEX = "scanner_rule_index"
    SCANNER_RULE_CATALOG = "scanner_rule_catalog"
    PROVIDER_GUIDANCE = "provider_guidance"
    CONTROL_FRAMEWORK = "control_framework"
    LOCAL_SCENARIO_DIR = "local_scenario_dir"
    LOCAL_RULE_CATALOG = "local_rule_catalog"
    IAC_REPO = "iac_repo"


class ReuseStatus(StrEnum):
    """How a source's material may be reused (design §3/§4, FXL-D007).

    ``mappings_only`` is training-eligible for control-ID mappings only (never control
    body text); ``restricted``/``metadata_only``/``unknown`` are NOT training-eligible.
    """

    FULL_REUSE = "full_reuse"
    ATTRIBUTION = "attribution"
    METADATA_ONLY = "metadata_only"
    MAPPINGS_ONLY = "mappings_only"
    RESTRICTED = "restricted"
    UNKNOWN = "unknown"


# reuse_status values that make a source ineligible for training export by default.
NON_TRAINING_REUSE: frozenset[ReuseStatus] = frozenset(
    {ReuseStatus.RESTRICTED, ReuseStatus.METADATA_ONLY, ReuseStatus.UNKNOWN}
)


class SourceEntry(BaseModel):
    """One allow-listed source (design §4).

    Exactly one of ``url`` (approved remote) or ``path`` (local, no network) is set. A
    model validator enforces that; the loader additionally applies governance rules.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    type: SourceType
    url: str | None = None
    path: str | None = None
    adapter: str
    enabled: bool
    license: str
    reuse_status: ReuseStatus
    allowed_for_training: bool
    notes: str = ""

    @model_validator(mode="after")
    def _exactly_one_location(self) -> SourceEntry:
        if bool(self.url) == bool(self.path):
            raise ValueError(f"source {self.id!r} must set exactly one of url/path")
        return self

    @property
    def location(self) -> str:
        """The source's ``url`` or ``path`` (exactly one is set)."""
        return self.url or self.path or ""


class SourceRegistry(BaseModel):
    """The full allow-list plus id lookup helpers."""

    model_config = ConfigDict(extra="forbid")

    sources: list[SourceEntry]

    @model_validator(mode="after")
    def _unique_ids(self) -> SourceRegistry:
        ids = [entry.id for entry in self.sources]
        if len(ids) != len(set(ids)):
            dupes = sorted({sid for sid in ids if ids.count(sid) > 1})
            raise ValueError(f"duplicate source id(s): {dupes}")
        return self

    def by_id(self, source_id: str) -> SourceEntry | None:
        """Return the entry with ``source_id``, or ``None`` if unlisted."""
        return next((e for e in self.sources if e.id == source_id), None)

    def enabled_entries(self) -> list[SourceEntry]:
        """Return only ``enabled: true`` entries (the fetcher's working set)."""
        return [e for e in self.sources if e.enabled]


class RawCacheMetadata(BaseModel):
    """Sidecar metadata for a cached raw fetch (design §4, rule 6).

    Written next to the raw bytes at ``data/raw/<source_id>/<content_hash>`` by the
    fetcher (ticket #62 in the design's numbering / #2). Content-addressed so the fetch
    is idempotent. Timestamps are passed in (never defaulted at import time).
    """

    model_config = ConfigDict(extra="forbid")

    source_id: str
    source_url_or_path: str
    fetched_at: str
    http_status: int | None = None
    content_type: str | None = None
    content_hash: str
    size_bytes: int
