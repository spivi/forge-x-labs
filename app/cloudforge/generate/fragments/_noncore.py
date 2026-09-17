"""Small builders shared by the vendor non-core fragments.

The Azure, GCP and Kubernetes noise / decoy / false-positive / compensating-control
fragments all mint the same shapes: a tagged node whose id slug is its vocabulary
name, a benign edge, a one-node bundle. Keeping the builders here keeps each vendor
module down to its story. Tags are drawn from the fixed ``_vocab`` lists with the
fragment rng, like ``benign_noise.py`` does for the AWS pool.
"""

from __future__ import annotations

from random import Random

from app.cloudforge.generate.fragments._vocab import (
    APP_VALUES,
    CLASSIFICATIONS,
    ENV_VALUES,
    OWNER_VALUES,
)
from app.cloudforge.generate.fragments.base import FragmentBundle
from app.cloudforge.models.findings import ExpectedFinding, GroundTruthPath
from app.cloudforge.models.graph import (
    Criticality,
    EdgeRisk,
    EdgeSecurity,
    EdgeType,
    GraphEdge,
    GraphNode,
    NodeSecurity,
    NodeTags,
    NodeType,
)


def draw_tags(rng: Random) -> NodeTags:
    return NodeTags(
        env=rng.choice(ENV_VALUES), owner=rng.choice(OWNER_VALUES), app=rng.choice(APP_VALUES)
    )


def node(
    ns: str,
    name: str,
    ntype: NodeType,
    tags: NodeTags,
    crit: Criticality = "low",
    **attrs: str | list[str],
) -> GraphNode:
    """A node whose id slug is its own name, the shape the vendor core fragments use."""
    return GraphNode(
        id=f"{ns}/{name}",
        type=ntype,
        name=name,
        tags=tags,
        security=NodeSecurity(criticality=crit),
        attributes=dict(attrs),
    )


def edge(src: GraphNode, dst: GraphNode, etype: EdgeType, risk: EdgeRisk = "low") -> GraphEdge:
    return GraphEdge(from_=src.id, to=dst.id, type=etype, security=EdgeSecurity(risk=risk))


def data_set(
    ns: str, name: str, tags: NodeTags, classification: str, crit: Criticality = "low"
) -> GraphNode:
    """A data set at ``classification``; draw it with ``draw_classification`` unless
    the fragment's story fixes it (a compensating control guards restricted data)."""
    return node(ns, name, NodeType.DATASET, tags, crit, classification=classification)


def draw_classification(rng: Random) -> str:
    return rng.choice(CLASSIFICATIONS)


def bundle(
    nodes: list[GraphNode],
    edges: list[GraphEdge] | None = None,
    findings: list[ExpectedFinding] | None = None,
    paths: list[GroundTruthPath] | None = None,
) -> FragmentBundle:
    return FragmentBundle(
        nodes=nodes, edges=edges or [], findings=findings or [], paths=paths or []
    )
