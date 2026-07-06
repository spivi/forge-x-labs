"""Individual scoring dimensions for ``quality.py`` (design §9.4).

Split out of ``quality.py`` to keep that module within the 200-line cap
(rules/general.md). Each function returns a plain ``float`` in ``[0, 1]`` and is a
pure function of the pattern's own fields — no ML, no embeddings, no randomness.
"""

from __future__ import annotations

from app.cloudforge.learn.pattern_models import PatternProvenance, RiskPattern

# --- provenance completeness -------------------------------------------------------

# Required, free-text provenance fields whose presence signals a well-documented
# source (mirrors normalizer._REQUIRED_PROVENANCE_STRINGS plus the two timestamps
# and content hash, which are always non-blank by construction but checked anyway
# for robustness against hand-built/legacy patterns).
_PROVENANCE_STRING_FIELDS: tuple[str, ...] = (
    "source_id",
    "source_name",
    "source_url_or_path",
    "source_license",
    "extraction_method",
    "content_hash",
    "adapter_name",
    "adapter_version",
    "normalizer_version",
)


def provenance_completeness_score(pattern: RiskPattern) -> float:
    """Fraction of required provenance fields that are non-blank, plus notes credit."""
    provenance = pattern.provenance
    present = sum(1 for field in _PROVENANCE_STRING_FIELDS if _is_set(provenance, field))
    base = present / len(_PROVENANCE_STRING_FIELDS)
    bonus = 0.1 if provenance.notes.strip() else 0.0
    return min(1.0, base + bonus)


def _is_set(provenance: PatternProvenance, field: str) -> bool:
    return bool(getattr(provenance, field).strip())


# --- fragment richness --------------------------------------------------------------

_MIN_RICH_NODES = 4
_MIN_RICH_EDGES = 2


def fragment_richness_score(pattern: RiskPattern) -> float:
    """Score a fragment's structural richness: >=2 nodes and >=1 edge is the floor.

    An empty fragment scores 0; a single-node/edge-less fragment scores low; a
    fragment meeting the >=2 nodes / >=1 edge bar scores 0.6, rising toward 1.0 as
    node/edge counts grow (capped at ``_MIN_RICH_NODES``/``_MIN_RICH_EDGES``).
    """
    fragment = pattern.graph_fragment
    node_count = len(fragment.nodes)
    edge_count = len(fragment.edges)

    if node_count == 0:
        return 0.0
    if node_count < 2 or edge_count < 1:
        return 0.2

    node_ratio = min(1.0, node_count / _MIN_RICH_NODES)
    edge_ratio = min(1.0, edge_count / _MIN_RICH_EDGES)
    return round(0.6 + 0.2 * node_ratio + 0.2 * edge_ratio, 4)


# --- findings coverage ---------------------------------------------------------------

_MIN_RICH_FINDINGS = 2


def findings_coverage_score(pattern: RiskPattern) -> float:
    """Score whether >=1 ``ExpectedFinding`` references a node in the fragment."""
    node_ids = {node.id for node in pattern.graph_fragment.nodes}
    referencing = [
        finding
        for finding in pattern.expected_findings
        if node_ids.intersection(finding.resource_ids)
    ]
    if not referencing:
        return 0.0
    ratio = min(1.0, len(referencing) / _MIN_RICH_FINDINGS)
    return round(0.5 + 0.5 * ratio, 4)


# --- control mapping -------------------------------------------------------------------


def control_mapping_score(pattern: RiskPattern) -> float:
    """Score presence of ``control_mappings`` and/or ``missing_controls``."""
    has_mappings = bool(pattern.control_mappings)
    has_missing = bool(pattern.missing_controls)
    if has_mappings and has_missing:
        return 1.0
    if has_mappings or has_missing:
        return 0.6
    return 0.0


# --- realism ---------------------------------------------------------------------------

# Severities that plausibly warrant a rich fragment + explicit risky relationships;
# a high/critical pattern with neither is an incoherent combination (design §9.4).
_HIGH_SEVERITIES = frozenset({"high", "critical"})

# A relationship count beyond this, on a pattern with no affected resource types at
# all, reads as an implausible combination (relationships without resources).
_MAX_PLAUSIBLE_RELATIONSHIPS_WITHOUT_RESOURCES = 1


def realism_score(pattern: RiskPattern) -> float:
    """Score plausibility of the resource-type + relationship + severity combination.

    Starts at a neutral baseline and applies deterministic penalties for
    incoherent combinations: a high/critical-severity pattern with an empty (or
    edge-less) fragment and no risky relationships is not a realistic
    representation of that severity; relationships claimed with zero affected
    resource types are similarly implausible.
    """
    score = 0.7

    if pattern.severity in _HIGH_SEVERITIES:
        if not pattern.graph_fragment.nodes and not pattern.risky_relationships:
            score -= 0.5
        elif not pattern.graph_fragment.edges and not pattern.risky_relationships:
            score -= 0.25
        else:
            score += 0.15

    if (
        len(pattern.risky_relationships) > _MAX_PLAUSIBLE_RELATIONSHIPS_WITHOUT_RESOURCES
        and not pattern.affected_resource_types
    ):
        score -= 0.3

    if pattern.affected_resource_types and pattern.graph_fragment.nodes:
        score += 0.1

    return round(min(1.0, max(0.0, score)), 4)
