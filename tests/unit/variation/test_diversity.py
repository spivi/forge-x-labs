"""Unit tests for the graph-shape signature + diversity report.

Core adversarial contract (per the diversity model's acceptance criteria): a purely
cosmetic mutation (names/tags/one benign-additive node) must NOT change the
signature; a genuine scale-profile change MUST change it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.cloudforge.generate.composer import GraphComposer
from app.cloudforge.generate.mutation_generator import MutationGenerator
from app.cloudforge.io.loaders import load_yaml
from app.cloudforge.models.scenario import ScenarioSpec
from app.cloudforge.variation.diversity import diversity_report, shape_signature


def _spec(scenario_type: str = "ci_cd_iam_chain", scale: str = "small") -> ScenarioSpec:
    fname = (
        "ci_cd_iam_chain.yaml"
        if scenario_type == "ci_cd_iam_chain"
        else ("public_data_exposure.yaml")
    )
    data = load_yaml(Path("examples") / fname)
    data["scale_profile"] = scale
    return ScenarioSpec.model_validate(data)


def test_cosmetic_mutation_same_signature() -> None:
    base = GraphComposer(_spec(), seed=1).generate()
    mutated = MutationGenerator(base, seed=42).generate()
    assert shape_signature(base, "ci_cd_iam_chain") == shape_signature(mutated, "ci_cd_iam_chain")


def test_cosmetic_mutation_same_signature_across_several_seeds() -> None:
    """Adversarial: several mutation seeds, not just one lucky draw."""
    base = GraphComposer(_spec(), seed=3).generate()
    base_sig = shape_signature(base, "ci_cd_iam_chain")
    for mutation_seed in (1, 2, 5, 17, 99):
        mutated = MutationGenerator(base, seed=mutation_seed).generate()
        assert shape_signature(mutated, "ci_cd_iam_chain") == base_sig


@pytest.mark.parametrize("family", ["ci_cd_iam_chain", "public_data_exposure"])
@pytest.mark.parametrize("compose_seed", [1, 2, 7])
def test_cosmetic_mutation_same_signature_every_family(family: str, compose_seed: int) -> None:
    """The core AC across BOTH families: a cosmetic mutation must preserve the signature.

    Regression guard for the case where the mutation engine injects a benign Subnet the
    base family lacks (``public_data_exposure`` has no Subnet); the injected node/edge
    must be canonicalized out so the signature is unchanged. Without the fix, every
    ``public_data_exposure`` mutation flipped the signature (0->1 count-bucket cross).
    """
    base = GraphComposer(_spec(family), seed=compose_seed).generate()
    base_sig = shape_signature(base, family)
    for mutation_seed in (1, 2, 5, 17, 99):
        mutated = MutationGenerator(base, seed=mutation_seed).generate()
        assert shape_signature(mutated, family) == base_sig, (
            f"{family} seed={compose_seed} mutation={mutation_seed}: "
            "cosmetic mutation changed the shape signature"
        )


def test_different_scale_different_signature() -> None:
    a = GraphComposer(_spec(scale="tiny"), seed=1).generate()
    b = GraphComposer(_spec(scale="medium"), seed=1).generate()
    assert shape_signature(a, "ci_cd_iam_chain") != shape_signature(b, "ci_cd_iam_chain")


def test_different_family_different_signature_even_at_same_scale() -> None:
    a = GraphComposer(_spec("ci_cd_iam_chain", "small"), seed=1).generate()
    b = GraphComposer(_spec("public_data_exposure", "small"), seed=1).generate()
    assert shape_signature(a, "ci_cd_iam_chain") != shape_signature(b, "public_data_exposure")


def test_signature_excludes_names_and_tags_directly() -> None:
    """Rename every node/retag it by hand (no mutation engine) -> same signature."""
    base = GraphComposer(_spec(), seed=5).generate()
    renamed_nodes = [
        n.model_copy(update={"name": f"renamed-{i}"}) for i, n in enumerate(base.graph.nodes)
    ]
    renamed_graph = base.graph.model_copy(update={"nodes": renamed_nodes})
    renamed_bundle = base.model_copy(update={"graph": renamed_graph})
    assert shape_signature(base, "ci_cd_iam_chain") == shape_signature(
        renamed_bundle, "ci_cd_iam_chain"
    )


def test_signature_is_deterministic() -> None:
    a = GraphComposer(_spec(), seed=9).generate()
    assert shape_signature(a, "ci_cd_iam_chain") == shape_signature(a, "ci_cd_iam_chain")


def test_report_counts_unique_signatures() -> None:
    bundles = [
        ("ci_cd_iam_chain", GraphComposer(_spec(scale="tiny"), seed=s).generate())
        for s in range(8)
    ]
    rep = diversity_report(bundles)
    assert rep["total_scenarios"] == 8
    assert rep["unique_graph_shapes"] >= 1


def test_report_distributions_present() -> None:
    bundles = [
        ("ci_cd_iam_chain", GraphComposer(_spec(scale="small"), seed=s).generate())
        for s in range(10)
    ]
    rep = diversity_report(bundles)
    assert "critical_path_lengths" in rep
    assert "scanner_score_profiles" in rep
    assert "pct_with_decoys" in rep
    assert "pct_with_compensating_controls" in rep
    assert "pct_with_false_positives" in rep


def test_report_decoy_percentage_reflects_axis_override() -> None:
    zero_decoy_spec = _spec(scale="small")
    zero_decoy_spec.variation_axes.update({"decoy": "0"})
    bundles = [
        ("ci_cd_iam_chain", GraphComposer(zero_decoy_spec, seed=s).generate()) for s in range(5)
    ]
    rep = diversity_report(bundles)
    assert rep["pct_with_decoys"] == 0.0


def test_report_marks_unsupported_axis_honestly() -> None:
    """public_data_exposure has a fixed-length critical path: the path-length
    axis genuinely cannot vary for this family. The report must say so, not
    silently omit or fake a count."""
    bundles = [
        (
            "public_data_exposure",
            GraphComposer(_spec("public_data_exposure", "small"), seed=s).generate(),
        )
        for s in range(5)
    ]
    rep = diversity_report(bundles, axes=["path_length"])
    assert "public_data_exposure" in rep["unsupported_axes"]
    assert "path_length" in rep["unsupported_axes"]["public_data_exposure"]


def test_report_does_not_mark_supported_axis_unsupported() -> None:
    """ci_cd_iam_chain DOES vary critical-path length across seeds (path_hops
    is randomized 3-5) -- it must not be reported unsupported."""
    bundles = [
        ("ci_cd_iam_chain", GraphComposer(_spec("ci_cd_iam_chain", "small"), seed=s).generate())
        for s in range(20)
    ]
    rep = diversity_report(bundles, axes=["path_length"])
    assert "path_length" not in rep["unsupported_axes"].get("ci_cd_iam_chain", [])


def test_report_empty_bundles_does_not_crash() -> None:
    rep = diversity_report([])
    assert rep["total_scenarios"] == 0
    assert rep["unique_graph_shapes"] == 0
