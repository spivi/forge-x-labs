"""Load, validate, and govern the source registry (``data/source_registry.yaml``).

``load_registry`` parses the allow-list, validates each entry with pydantic, and
applies the design §4 governance rules as a normalization step so the effective
``allowed_for_training`` on every entry is trustworthy regardless of what the YAML
declared:

1. ``license: unknown`` -> force ``allowed_for_training = false``.
2. ``reuse_status: restricted`` -> force ``allowed_for_training = false`` (export drops it).
3. ``reuse_status: metadata_only`` -> force ``allowed_for_training = false``.
4. ``reuse_status: mappings_only`` -> leave as-declared (CCM control-ID
   mappings may be training-eligible).

Anything else (``full_reuse`` / ``attribution``) keeps its declared flag. A malformed
registry raises ``RegistryError``.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from app.cloudforge.errors import CloudforgeError
from app.cloudforge.io.loaders import load_yaml
from app.cloudforge.learn.source_models import ReuseStatus, SourceEntry, SourceRegistry

_UNKNOWN_LICENSE = "unknown"

# reuse_status values that force allowed_for_training=false during governance.
_FORCE_FALSE_REUSE: frozenset[ReuseStatus] = frozenset(
    {ReuseStatus.RESTRICTED, ReuseStatus.METADATA_ONLY}
)


class RegistryError(CloudforgeError):
    """The source registry is missing, unreadable, or fails schema/governance validation."""


def _govern_entry(entry: SourceEntry) -> SourceEntry:
    """Apply the design §4 governance rules, returning a normalized copy."""
    allowed = entry.allowed_for_training
    if entry.license.strip().lower() == _UNKNOWN_LICENSE:
        allowed = False
    if entry.reuse_status in _FORCE_FALSE_REUSE:
        allowed = False
    if allowed == entry.allowed_for_training:
        return entry
    return entry.model_copy(update={"allowed_for_training": allowed})


def load_registry(path: str | Path) -> SourceRegistry:
    """Parse, validate, and govern the source registry at ``path``.

    Raises ``RegistryError`` if the file is unreadable, is not a ``sources:`` mapping,
    or any entry fails schema validation.
    """
    registry_path = Path(path)
    try:
        raw = load_yaml(registry_path)
    except CloudforgeError as exc:
        raise RegistryError(f"cannot load source registry {registry_path}: {exc}") from exc

    sources = raw.get("sources")
    if not isinstance(sources, list):
        raise RegistryError(f"registry {registry_path} must contain a 'sources' list")

    try:
        registry = SourceRegistry.model_validate({"sources": sources})
    except ValidationError as exc:
        raise RegistryError(f"invalid source registry {registry_path}: {exc}") from exc

    governed = [_govern_entry(entry) for entry in registry.sources]
    return SourceRegistry(sources=governed)


def get_entry(registry: SourceRegistry, source_id: str) -> SourceEntry:
    """Return the entry for ``source_id`` or raise ``RegistryError`` if unlisted."""
    entry = registry.by_id(source_id)
    if entry is None:
        raise RegistryError(f"source {source_id!r} is not in the registry (unlisted)")
    return entry


def enabled_sources(registry: SourceRegistry) -> list[SourceEntry]:
    """Return only the ``enabled: true`` entries (the fetcher's working set)."""
    return registry.enabled_entries()
