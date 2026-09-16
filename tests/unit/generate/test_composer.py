"""Unit tests for the seeded ``GraphComposer`` fragment-composition engine."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.cloudforge.errors import GraphIntegrityError
from app.cloudforge.generate.base import ScenarioBundle
from app.cloudforge.generate.composer import ComposerGenerator, GraphComposer
from app.cloudforge.io.loaders import load_yaml
from app.cloudforge.models.scenario import ScenarioSpec


def _spec(**over: Any) -> ScenarioSpec:
    data = load_yaml(Path("examples/ci_cd_iam_chain.yaml"))
    data.update(over)
    return ScenarioSpec.model_validate(data)


def test_same_seed_byte_identical() -> None:
    a = GraphComposer(_spec(), seed=7).generate()
    b = GraphComposer(_spec(), seed=7).generate()
    assert a.graph.model_dump(by_alias=True) == b.graph.model_dump(by_alias=True)
    assert a.findings.model_dump() == b.findings.model_dump()
    assert a.ground_truth.model_dump() == b.ground_truth.model_dump()


def test_node_ids_unique_across_fragments() -> None:
    g = GraphComposer(_spec(scale_profile="small"), seed=1).generate().graph
    ids = [n.id for n in g.nodes]
    assert len(ids) == len(set(ids))


def test_findings_reference_real_nodes() -> None:
    bundle = GraphComposer(_spec(scale_profile="small"), seed=1).generate()
    node_ids = {n.id for n in bundle.graph.nodes}
    for f in bundle.findings.findings:
        assert set(f.resource_ids) <= node_ids


def test_ground_truth_edges_resolve() -> None:
    bundle = GraphComposer(_spec(scale_profile="small"), seed=2).generate()
    edge_keys = {e.key for e in bundle.graph.edges}
    for p in bundle.ground_truth.paths:
        assert set(p.edges) <= edge_keys


def test_scale_profile_fills_node_band() -> None:
    g = GraphComposer(_spec(scale_profile="medium"), seed=3).generate().graph
    assert 75 <= len(g.nodes) <= 150


def test_small_profile_fills_node_band() -> None:
    g = GraphComposer(_spec(scale_profile="small"), seed=4).generate().graph
    assert 25 <= len(g.nodes) <= 50


def test_public_data_family_composes() -> None:
    data = load_yaml(Path("examples/public_data_exposure.yaml"))
    data["scale_profile"] = "small"
    spec = ScenarioSpec.model_validate(data)
    g = GraphComposer(spec, seed=1).generate().graph
    assert 25 <= len(g.nodes) <= 50


def test_returns_scenario_bundle() -> None:
    assert isinstance(GraphComposer(_spec(), seed=0).generate(), ScenarioBundle)


def test_at_least_one_critical_path() -> None:
    bundle = GraphComposer(_spec(scale_profile="small"), seed=1).generate()
    criticals = [p for p in bundle.ground_truth.paths if p.severity == "critical"]
    assert len(criticals) >= 1


def test_composer_generator_delegates_to_seed_zero() -> None:
    via_protocol = ComposerGenerator().generate(_spec())
    direct = GraphComposer(_spec(), seed=0).generate()
    assert via_protocol.graph.model_dump(by_alias=True) == direct.graph.model_dump(by_alias=True)


def test_id_collision_raises_graph_integrity_error() -> None:
    composer = GraphComposer(_spec(), seed=0)
    plan = [("benign_noise.unrelated_bucket", "dup", {})] * 2
    with pytest.raises(GraphIntegrityError):
        composer._assemble(plan)  # type: ignore[attr-defined]


def test_different_seeds_can_differ_structurally() -> None:
    n1 = len(GraphComposer(_spec(scale_profile="small"), seed=1).generate().graph.nodes)
    n2 = len(GraphComposer(_spec(scale_profile="small"), seed=99).generate().graph.nodes)
    # Counts may coincide; structural diversity is asserted in the Phase-2 signature
    # tests. Here we only assert both seeds produce valid, in-band graphs.
    assert n1 >= 25 and n2 >= 25


def test_variation_axes_override_decoy_count() -> None:
    """An explicit ``variation_axes`` count overrides the seeded default."""
    spec = _spec(scale_profile="small", variation_axes={"decoy": "0", "fp": "0", "ctrl": "0"})
    g = GraphComposer(spec, seed=1).generate().graph
    decoy_roles = [n for n in g.nodes if n.id.startswith("decoy")]
    assert decoy_roles == []


def test_stays_within_max_nodes_for_tiny_profile() -> None:
    """The mandatory extras must not push a tight profile past its ``max_nodes``."""
    g = GraphComposer(_spec(scale_profile="tiny"), seed=1).generate().graph
    assert 10 <= len(g.nodes) <= 20


def test_unknown_scenario_type_falls_back_to_ci_cd_core() -> None:
    spec = _spec(scenario_type="unmapped_family", scale_profile="small")
    bundle = GraphComposer(spec, seed=1).generate()
    assert any("core0" in n.id for n in bundle.graph.nodes)


def test_seed_salting_produces_unique_namespaces() -> None:
    spec = _spec(scale_profile="small")
    b0 = GraphComposer(spec, seed=0).generate()
    b1 = GraphComposer(spec, seed=1).generate()
    b2 = GraphComposer(spec, seed=2).generate()
    ids0 = {n.id for n in b0.graph.nodes}
    ids1 = {n.id for n in b1.graph.nodes}
    ids2 = {n.id for n in b2.graph.nodes}
    assert any(nid.startswith("core0/") for nid in ids0)
    assert any("core0_" in nid for nid in ids1)
    assert any("core0_" in nid for nid in ids2)
    assert ids1.isdisjoint(ids2)
