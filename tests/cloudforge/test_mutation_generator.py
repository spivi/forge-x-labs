"""Mutation-engine tests (FXL-14).

Covers: valid bundle out, seed determinism (byte-identical graph.json), stable
ground-truth ids across seeds, and the risk engine passing on >=3 seeded variants.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.cloudforge.generate.base import ScenarioBundle
from app.cloudforge.generate.mutation_generator import MutationGenerator
from app.cloudforge.generate.template_generator import TemplateGenerator
from app.cloudforge.models.scenario import ScenarioSpec
from app.cloudforge.validate.graph_risk import GraphRiskEngine
from app.cloudforge.validate.results import Status

_SEEDS = (1, 7, 42, 1337)


def _base(spec: ScenarioSpec) -> ScenarioBundle:
    return TemplateGenerator().generate(spec)


def _graph_json(bundle: ScenarioBundle) -> str:
    return json.dumps(bundle.graph.model_dump(by_alias=True), indent=2, sort_keys=False)


def test_generate_returns_valid_bundle(example_spec: ScenarioSpec) -> None:
    mutated = MutationGenerator(_base(example_spec), seed=1).generate()

    assert isinstance(mutated, ScenarioBundle)
    assert len(mutated.graph.nodes) > 0
    assert len(mutated.graph.edges) > 0


def test_same_seed_is_byte_identical(example_spec: ScenarioSpec) -> None:
    base = _base(example_spec)

    first = MutationGenerator(base, seed=42).generate()
    second = MutationGenerator(base, seed=42).generate()

    assert _graph_json(first) == _graph_json(second)


def test_different_seed_changes_names(example_spec: ScenarioSpec) -> None:
    base = _base(example_spec)

    variant_a = MutationGenerator(base, seed=1).generate()
    variant_b = MutationGenerator(base, seed=2).generate()

    assert _graph_json(variant_a) != _graph_json(variant_b)


def test_ground_truth_node_ids_stable_across_seeds(example_spec: ScenarioSpec) -> None:
    base = _base(example_spec)
    gt_ids = {nid for p in base.ground_truth.paths for nid in p.nodes}

    for seed in _SEEDS:
        mutated = MutationGenerator(base, seed=seed).generate()
        node_ids = {n.id for n in mutated.graph.nodes}
        assert gt_ids <= node_ids


def test_ground_truth_paths_and_findings_unchanged(example_spec: ScenarioSpec) -> None:
    base = _base(example_spec)

    mutated = MutationGenerator(base, seed=7).generate()

    assert mutated.ground_truth == base.ground_truth
    assert mutated.findings == base.findings


def test_mutation_renames_at_least_one_node(example_spec: ScenarioSpec) -> None:
    base = _base(example_spec)

    mutated = MutationGenerator(base, seed=99).generate()

    base_names = {n.id: n.name for n in base.graph.nodes}
    changed = [n.id for n in mutated.graph.nodes if base_names.get(n.id) not in (None, n.name)]
    assert changed


def test_mutation_stays_within_resource_budget(example_spec: ScenarioSpec) -> None:
    base = _base(example_spec)

    mutated = MutationGenerator(base, seed=5).generate()

    assert len(mutated.graph.nodes) <= example_spec.constraints.max_resources


@pytest.mark.parametrize("seed", _SEEDS)
def test_risk_engine_all_pass_on_variant(example_spec: ScenarioSpec, seed: int) -> None:
    base = _base(example_spec)

    mutated = MutationGenerator(base, seed=seed).generate()
    outcomes = GraphRiskEngine(mutated, example_spec).run()

    assert all(o.status is Status.PASS for o in outcomes), [
        (o.label, o.status) for o in outcomes if o.status is not Status.PASS
    ]


@pytest.mark.parametrize("seed", _SEEDS)
def test_no_forbidden_or_broad_grant_regression(example_spec: ScenarioSpec, seed: int) -> None:
    base = _base(example_spec)

    mutated = MutationGenerator(base, seed=seed).generate()
    outcomes = {o.label: o.status for o in GraphRiskEngine(mutated, example_spec).run()}

    assert outcomes["no forbidden permissions"] is Status.PASS
    assert outcomes["broad grants documented by findings"] is Status.PASS


def test_added_benign_node_is_within_budget_and_not_a_policy(example_spec: ScenarioSpec) -> None:
    from app.cloudforge.models.graph import NodeType

    base = _base(example_spec)

    mutated = MutationGenerator(base, seed=3).generate()

    added = [n for n in mutated.graph.nodes if n.id not in {b.id for b in base.graph.nodes}]
    for node in added:
        assert node.type is not NodeType.IAM_POLICY


def test_benign_node_skipped_when_at_budget(example_spec: ScenarioSpec) -> None:
    base = _base(example_spec)
    at_budget = len(base.graph.nodes)

    mutated = MutationGenerator(base, seed=3, max_resources=at_budget).generate()

    assert len(mutated.graph.nodes) == at_budget


def test_cli_mutate_seed_produces_all_pass_scenario(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from app.cli import app
    from app.cloudforge.validate import tool_probe

    runner = CliRunner()
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(tool_probe, "detect_tool", lambda name: False)
    out = tmp_path / "variant_001"

    gen = runner.invoke(
        app,
        ["generate", "examples/ci_cd_iam_chain.yaml", "--out", str(out), "--mutate-seed", "1"],
    )
    val = runner.invoke(app, ["validate", str(out)])
    monkeypatch.undo()

    assert gen.exit_code == 0, gen.output
    assert val.exit_code == 0, val.output


def test_cli_same_mutate_seed_is_byte_identical(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from app.cli import app

    runner = CliRunner()
    out_a = tmp_path / "a"
    out_b = tmp_path / "b"

    runner.invoke(
        app,
        ["generate", "examples/ci_cd_iam_chain.yaml", "--out", str(out_a), "--mutate-seed", "42"],
    )
    runner.invoke(
        app,
        ["generate", "examples/ci_cd_iam_chain.yaml", "--out", str(out_b), "--mutate-seed", "42"],
    )

    assert (out_a / "graph.json").read_text() == (out_b / "graph.json").read_text()
