"""Pairwise Jaccard similarity and collision bounds tests.

Guarantees that across arbitrary seeds and scenario families, pairwise similarity
remains strictly under 30%, preventing cohort cheating and template collisions.
"""

from __future__ import annotations

import itertools
from pathlib import Path

from app.cloudforge.generate.composer import GraphComposer
from app.cloudforge.io.loaders import load_yaml
from app.cloudforge.models.scenario import ScenarioSpec


def _load_specs() -> list[ScenarioSpec]:
    examples = sorted(Path("examples").glob("*.yaml"))
    return [ScenarioSpec.model_validate(load_yaml(p)) for p in examples]


def test_seeded_estates_have_zero_node_id_collision() -> None:
    """Distinct non-zero seeds must have completely disjoint node IDs."""
    spec = _load_specs()[0]
    bundles = [GraphComposer(spec, seed=s).generate() for s in range(1, 11)]
    for b1, b2 in itertools.combinations(bundles, 2):
        ids1 = {n.id for n in b1.graph.nodes}
        ids2 = {n.id for n in b2.graph.nodes}
        assert ids1.isdisjoint(ids2), f"collision detected between seeds: {ids1 & ids2}"


def test_unnamespaced_structural_similarity_under_thirty_percent() -> None:
    """Even stripping all namespace prefixes, pairwise Jaccard similarity must stay < 30%."""
    spec = _load_specs()[0]
    bundles = [GraphComposer(spec, seed=s * 13 + 7).generate() for s in range(15)]
    similarities: list[float] = []
    for b1, b2 in itertools.combinations(bundles, 2):
        t1 = {
            (n.type.value, n.name, tuple(sorted(n.tags.model_dump().items())))
            for n in b1.graph.nodes
        }
        t2 = {
            (n.type.value, n.name, tuple(sorted(n.tags.model_dump().items())))
            for n in b2.graph.nodes
        }
        jaccard = len(t1 & t2) / len(t1 | t2) if (t1 | t2) else 0.0
        similarities.append(jaccard)

    max_sim = max(similarities)
    assert max_sim < 0.30, f"max un-namespaced similarity {max_sim:.2%} exceeded 30% bound"


def test_cross_family_similarity_under_thirty_percent() -> None:
    """Pairwise similarity across distinct families must stay strictly < 30%."""
    specs = _load_specs()
    bundles = [GraphComposer(s, seed=idx * 5 + 3).generate() for idx, s in enumerate(specs)]
    for b1, b2 in itertools.combinations(bundles, 2):
        t1 = {
            (n.type.value, n.name, tuple(sorted(n.tags.model_dump().items())))
            for n in b1.graph.nodes
        }
        t2 = {
            (n.type.value, n.name, tuple(sorted(n.tags.model_dump().items())))
            for n in b2.graph.nodes
        }
        jaccard = len(t1 & t2) / len(t1 | t2) if (t1 | t2) else 0.0
        assert jaccard < 0.30, f"cross-family similarity {jaccard:.2%} exceeded 30% bound"
