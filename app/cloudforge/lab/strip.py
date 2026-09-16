"""Strip answer-key fields from a scenario graph for the student pack (FXL-D010)."""

from __future__ import annotations

from typing import Any

from app.cloudforge.models.graph import GraphEdge, GraphNode, ScenarioGraph


def strip_graph(graph: ScenarioGraph) -> dict[str, Any]:
    """Return a JSON-ready estate with no ``security`` / criticality / risk labels."""
    return {
        "nodes": [_strip_node(node) for node in graph.nodes],
        "edges": [_strip_edge(edge) for edge in graph.edges],
    }


def _strip_node(node: GraphNode) -> dict[str, Any]:
    return {
        "id": node.id,
        "type": node.type.value,
        "name": node.name,
        "tags": node.tags.model_dump(),
        "attributes": dict(node.attributes),
    }


def _strip_edge(edge: GraphEdge) -> dict[str, Any]:
    return {"from": edge.from_, "to": edge.to, "type": edge.type.value}
