"""The ``PatternAdapter`` protocol — the shape every source adapter satisfies.

An adapter reads a cached raw source (bytes/dir on disk, no network) plus its registry
entry and emits a list of ``RawPatternRecord``s, stamping its own ``adapter_name`` /
``adapter_version`` into each record's provenance. The normalizer (later) turns those
records into ``RiskPattern``s. This is a structural protocol so concrete adapters need
not inherit from a base class — they just match ``extract`` (design §8).
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from app.cloudforge.learn.pattern_models import RawPatternRecord
from app.cloudforge.learn.source_models import SourceEntry


@runtime_checkable
class PatternAdapter(Protocol):
    """Extract ``RawPatternRecord``s from one cached, registry-listed source."""

    #: stable adapter identity, stamped into provenance for reproducibility.
    adapter_name: str
    adapter_version: str

    def extract(self, source: SourceEntry, raw_path: Path) -> list[RawPatternRecord]:
        """Return the records extracted from ``raw_path`` for ``source``.

        ``raw_path`` is a local, already-fetched cache location (never the network).
        Implementations must respect the source's ``reuse_status`` (e.g. a
        ``metadata_only`` source must never copy rule source text into a record).
        """
        ...
