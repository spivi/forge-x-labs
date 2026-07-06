"""``ingest`` helpers: adapter-name resolution + cached raw-path lookup (design §10).

Kept out of ``cli.py`` to hold that module's line count down (rules/general.md).
A source is either local (``SourceEntry.path`` — read directly, no fetch step) or
remote (``SourceEntry.url`` — read from the most recently fetched cache file under
``data/raw/<source_id>/``, written by ``fetch.py``).
"""

from __future__ import annotations

from pathlib import Path

from app.cloudforge.errors import CloudforgeError
from app.cloudforge.learn.adapters.base import PatternAdapter
from app.cloudforge.learn.adapters.checkov_policy_index import CheckovPolicyIndexAdapter
from app.cloudforge.learn.adapters.cloudforge_scenario import CloudforgeScenarioAdapter
from app.cloudforge.learn.adapters.rule_catalog_yaml import RuleCatalogYamlAdapter
from app.cloudforge.learn.source_models import SourceEntry

_METADATA_FILENAME = "metadata.json"

#: name -> adapter instance, keyed by each adapter's own ``ADAPTER_NAME``.
ADAPTERS: dict[str, PatternAdapter] = {
    RuleCatalogYamlAdapter.adapter_name: RuleCatalogYamlAdapter(),
    CheckovPolicyIndexAdapter.adapter_name: CheckovPolicyIndexAdapter(),
    CloudforgeScenarioAdapter.adapter_name: CloudforgeScenarioAdapter(),
}


class UnknownAdapterError(CloudforgeError):
    """``--adapter`` named something not in the adapter registry."""


class NoCachedRawSourceError(CloudforgeError):
    """A remote source has no fetched cache yet (``fetch-sources`` was not run)."""


class PathTraversalError(CloudforgeError):
    """A local source ``path`` resolves outside the allowed base directory."""


def resolve_adapter(name: str) -> PatternAdapter:
    """Return the adapter registered as ``name``, or raise ``UnknownAdapterError``."""
    adapter = ADAPTERS.get(name)
    if adapter is None:
        known = ", ".join(sorted(ADAPTERS))
        raise UnknownAdapterError(f"unknown adapter {name!r} (known adapters: {known})")
    return adapter


def resolve_raw_path(entry: SourceEntry, raw_dir: Path) -> Path:
    """Return the path an adapter should read for ``entry``.

    Local sources (``entry.path`` set) are read directly — no fetch step. Remote
    sources are read from their latest cached file under ``raw_dir/<source_id>/``.

    ``SourceEntry`` already refuses an escaping ``path`` at load time (its
    ``_path_stays_in_tree`` validator). This function adds a resolve-time containment
    guard as defense in depth: the local path is resolved against the current working
    directory (the project root the CLI is invoked from) and must stay inside it, so
    even a ``SourceEntry`` reaching here through a bypassed validator (e.g.
    ``model_construct``) cannot escape. Raises ``PathTraversalError`` on any escape.
    """
    if entry.path is not None:
        return _resolve_local_path(entry.path)
    return _latest_cached_file(entry, raw_dir)


def _resolve_local_path(raw_path: str) -> Path:
    """Resolve a local ``path`` and refuse anything outside the project root (CWD)."""
    base = Path.cwd().resolve()
    resolved = (base / raw_path).resolve()
    if not resolved.is_relative_to(base):
        raise PathTraversalError(
            f"local source path {raw_path!r} resolves to {resolved} which is outside "
            f"the allowed base directory {base}"
        )
    return resolved


def _latest_cached_file(entry: SourceEntry, raw_dir: Path) -> Path:
    source_dir = raw_dir / entry.id
    candidates = [p for p in source_dir.glob("*") if p.is_file() and p.name != _METADATA_FILENAME]
    if not candidates:
        raise NoCachedRawSourceError(
            f"no cached raw file for source {entry.id!r} under {source_dir} "
            "(run 'cloudforge learn fetch-sources' first)"
        )
    return max(candidates, key=lambda p: p.stat().st_mtime)
