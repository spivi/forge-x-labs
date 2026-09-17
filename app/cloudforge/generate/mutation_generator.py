"""Seeded, deterministic mutation engine.

``MutationGenerator`` produces cosmetic + benign-additive variants of a base
``ScenarioBundle`` so a scanner benchmark gets *diversity* without any change to the
ground-truth risk. It implements the ``ScenarioGenerator`` seam's contract shape
(returns a validated ``ScenarioBundle``) but takes an already-built base bundle plus
a seed rather than a spec, so it composes *after* the base generator.

Guarantees:
  * Deterministic — same ``seed`` yields a byte-identical ``graph.json`` (explicit
    ``random.Random(seed)``; never the global RNG, wall-clock, or PID).
  * Ground truth preserved — node ``id``s, edges, ground-truth paths, and expected
    findings are untouched; only display ``name``s, ``tags``, and one benign extra
    node/edge change. The risk engine still returns all-PASS on every variant.
"""

from __future__ import annotations

from random import Random

from app.cloudforge.generate import mutation_ops
from app.cloudforge.generate.base import ScenarioBundle
from app.cloudforge.models.graph import GraphEdge, GraphNode, ScenarioGraph

# How many spare resource slots to keep free before injecting the benign extra node.
_BUDGET_HEADROOM = 1


class MutationGenerator:
    """Turns a base bundle + seed into a seeded, ground-truth-preserving variant."""

    def __init__(self, base: ScenarioBundle, seed: int, max_resources: int | None = None) -> None:
        self._base = base
        self._seed = seed
        self._max_resources = max_resources

    def generate(self) -> ScenarioBundle:
        """Return a mutated bundle; ground truth and findings are carried through as-is."""
        rng = Random(self._seed)
        graph = self._mutate_graph(rng)
        return ScenarioBundle(
            graph=graph,
            findings=self._base.findings,
            ground_truth=self._base.ground_truth,
        )

    def _mutate_graph(self, rng: Random) -> ScenarioGraph:
        nodes = [mutation_ops.mutate_node(node, rng) for node in self._base.graph.nodes]
        edges = list(self._base.graph.edges)
        self._maybe_add_benign_context(nodes, edges, rng)
        return ScenarioGraph(nodes=nodes, edges=edges)

    def _maybe_add_benign_context(
        self, nodes: list[GraphNode], edges: list[GraphEdge], rng: Random
    ) -> None:
        if not self._has_budget_for_extra(len(nodes)):
            return
        subnet = mutation_ops.make_benign_subnet(rng)
        nodes.append(subnet)
        vpc_id = mutation_ops.find_vpc_id(self._base.graph)
        if vpc_id is not None:
            edges.append(mutation_ops.make_benign_edge(subnet.id, vpc_id))

    def _has_budget_for_extra(self, current_count: int) -> bool:
        if self._max_resources is None:
            return True
        return current_count + _BUDGET_HEADROOM <= self._max_resources
