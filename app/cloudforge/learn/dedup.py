"""Deterministic corpus dedup (design §9.3).

Two patterns are duplicates iff their deterministic dedup key matches:
``(cloud_provider, weakness_family, sorted affected_resource_types, sorted
risky_relationships, sorted missing_controls, sorted compensating_controls)``.

On a collision: keep the highest-``quality_score`` pattern (tie-broken deterministically
by ``id`` so the result is stable regardless of input order); merge the dropped
duplicates' ``source_mappings`` into the survivor (``RiskPattern`` has no dedicated
provenance-list field, so ``source_mappings`` — already a "mappings from other sources"
bag — is the natural home; see design §9.3, which explicitly allows this as an
alternative to a new field); and record the dropped ids in a separate ``DedupReport``
rather than mutating ``RiskPattern`` with a new field.

Same input corpus (any order) -> same survivors + same report. No fuzzy matching, no
embeddings (that would be ML) — exact key equality only.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.cloudforge.learn.pattern_models import RiskPattern

DedupKey = tuple[str, str, tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]]


class DedupReport(BaseModel):
    """Outcome of a :func:`dedup` run (design §9.3).

    ``groups`` maps a stringified dedup key to every pattern id that shared it
    (survivor first). ``dropped_duplicate_ids`` maps a surviving pattern's id to the
    ids of the duplicates dropped in its favor.
    """

    model_config = ConfigDict(extra="forbid")

    survivor_ids: list[str]
    dropped_duplicate_ids: dict[str, list[str]]
    groups: dict[str, list[str]]


def _dedup_key(pattern: RiskPattern) -> DedupKey:
    """Build the deterministic dedup key for ``pattern`` (design §9.3)."""
    return (
        pattern.cloud_provider.value,
        pattern.weakness_family.value,
        tuple(sorted(pattern.affected_resource_types)),
        tuple(sorted(pattern.risky_relationships)),
        tuple(sorted(pattern.missing_controls)),
        tuple(sorted(pattern.compensating_controls)),
    )


def _group_by_key(patterns: list[RiskPattern]) -> dict[DedupKey, list[RiskPattern]]:
    """Group patterns by their exact dedup key, preserving first-seen order per group."""
    groups: dict[DedupKey, list[RiskPattern]] = {}
    for pattern in patterns:
        groups.setdefault(_dedup_key(pattern), []).append(pattern)
    return groups


def _pick_survivor(group: list[RiskPattern]) -> RiskPattern:
    """Highest ``quality_score`` wins; ties break on ``id`` for order-independence."""
    return max(group, key=lambda p: (p.quality_score, p.id))


def _merge_survivor(survivor: RiskPattern, dropped: list[RiskPattern]) -> RiskPattern:
    """Merge dropped duplicates' ``source_mappings`` into the survivor (design §9.3)."""
    merged_mappings = set(survivor.source_mappings)
    for duplicate in dropped:
        merged_mappings.update(duplicate.source_mappings)
    return survivor.model_copy(update={"source_mappings": sorted(merged_mappings)})


def _resolve_group(group: list[RiskPattern]) -> tuple[RiskPattern, list[str]]:
    """Resolve one key-collision group into (merged survivor, dropped ids)."""
    ordered = sorted(group, key=lambda p: p.id)
    survivor = _pick_survivor(ordered)
    dropped = [p for p in ordered if p.id != survivor.id]
    dropped_ids = [p.id for p in dropped]
    return _merge_survivor(survivor, dropped), dropped_ids


def dedup(patterns: list[RiskPattern]) -> tuple[list[RiskPattern], DedupReport]:
    """Deterministically dedup ``patterns`` by exact key equality (design §9.3).

    Returns ``(survivors, report)``. ``survivors`` is sorted by id for a stable,
    order-independent result. No fuzzy matching, no embeddings.
    """
    groups = _group_by_key(patterns)

    survivors: list[RiskPattern] = []
    dropped_duplicate_ids: dict[str, list[str]] = {}
    report_groups: dict[str, list[str]] = {}

    for key, group in groups.items():
        survivor, dropped_ids = _resolve_group(group)
        survivors.append(survivor)
        if dropped_ids:
            dropped_duplicate_ids[survivor.id] = sorted(dropped_ids)
        report_groups[repr(key)] = [survivor.id, *sorted(dropped_ids)]

    survivors.sort(key=lambda p: p.id)
    report = DedupReport(
        survivor_ids=[p.id for p in survivors],
        dropped_duplicate_ids=dropped_duplicate_ids,
        groups=report_groups,
    )
    return survivors, report
