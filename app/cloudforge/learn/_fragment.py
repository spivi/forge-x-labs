"""Honest ``graph_fragment`` construction for the normalizer (design §9.1, FXL-96).

Split out of ``normalizer.py`` to keep that module under the 200-line cap
(rules/general.md). The normalizer does NOT invent a graph from a seed's flat fields
— a seed declares a risk *pattern*, not a graph — so this module only ever:

  1. reuses a real graph already embedded in ``raw_payload`` (the ``cloudforge_scenario``
     adapter stores its full ``ScenarioGraph`` as JSON there); or
  2. builds a minimal, un-fabricated fragment (one generic node per declared resource
     type, no edges) when no embedded graph exists (the rule-catalog seed path).

Hand-authored per-seed fragments land in a later ticket (#98). Purely deterministic —
no ML, no embeddings, no invented relationships.
"""

from __future__ import annotations

from app.cloudforge.learn.pattern_models import RawPatternRecord
from app.cloudforge.models.graph import GraphNode, NodeSecurity, NodeTags, NodeType, ScenarioGraph

_FRAGMENT_NODE_TAGS = NodeTags(env="unknown", owner="unknown", app="unknown")
_FRAGMENT_NODE_SECURITY = NodeSecurity(criticality="medium")


def _fragment_from_raw_payload(raw: RawPatternRecord) -> ScenarioGraph | None:
    """Reuse a real, already-validated graph embedded in ``raw_payload`` (design §9.1).

    The ``cloudforge_scenario`` adapter stores the full scenario graph as a
    JSON-encoded string under ``raw_payload["graph"]``; when present it is a richer,
    real fragment (with edges) and should be reused verbatim rather than rebuilt.
    """
    graph_json = raw.raw_payload.get("graph")
    if not isinstance(graph_json, str) or not graph_json:
        return None
    return ScenarioGraph.model_validate_json(graph_json)


def _minimal_fragment(resource_types: list[str]) -> ScenarioGraph:
    """Build an honest minimal fragment: one generic node per (deduped, sorted) type.

    No relationships can be inferred from a bare resource-type list without inventing
    cloud semantics the seed never declared (FXL-96 review), so no edges are emitted —
    an edge-less fragment is a valid ``ScenarioGraph`` (nothing to resolve). Real
    per-seed fragments are hand-authored in a later ticket (#98).
    """
    nodes = [
        GraphNode(
            id=f"resource-{index}",
            type=NodeType.APPLICATION,
            name=resource_type,
            tags=_FRAGMENT_NODE_TAGS,
            security=_FRAGMENT_NODE_SECURITY,
            attributes={"resource_type": resource_type},
        )
        for index, resource_type in enumerate(sorted(set(resource_types)))
    ]
    return ScenarioGraph(nodes=nodes, edges=[])


def build_graph_fragment(raw: RawPatternRecord) -> ScenarioGraph:
    """Reuse an embedded graph if present, else build a minimal fragment (design §9.1)."""
    embedded = _fragment_from_raw_payload(raw)
    if embedded is not None:
        return embedded
    return _minimal_fragment(raw.resource_types)
