"""Leak tests for the student-facing graph strip (FXL-D010 / FXL-144)."""

from __future__ import annotations

from pathlib import Path

from app.cloudforge.generate.composer import GraphComposer
from app.cloudforge.io.loaders import load_yaml
from app.cloudforge.lab.strip import strip_graph
from app.cloudforge.models.scenario import ScenarioSpec


def _bundle(family: str = "ci_cd_iam_chain", seed: int = 17):
    data = load_yaml(Path("examples") / f"{family}.yaml")
    spec = ScenarioSpec.model_validate(data)
    return GraphComposer(spec, seed).generate()


def test_stripped_nodes_have_no_security() -> None:
    estate = strip_graph(_bundle().graph)
    assert estate["nodes"]
    for node in estate["nodes"]:
        assert "security" not in node
        assert "criticality" not in node


def test_stripped_edges_have_no_security() -> None:
    estate = strip_graph(_bundle().graph)
    assert estate["edges"]
    for edge in estate["edges"]:
        assert "security" not in edge
        assert "risk" not in edge
        assert "from" in edge and "to" in edge and "type" in edge


def test_stripped_estate_keeps_ids_types_and_actions() -> None:
    bundle = _bundle()
    estate = strip_graph(bundle.graph)
    ids = {n["id"] for n in estate["nodes"]}
    assert {n.id for n in bundle.graph.nodes} == ids
    sample = next(n for n in estate["nodes"] if n["attributes"])
    assert "id" in sample and "type" in sample and "name" in sample
