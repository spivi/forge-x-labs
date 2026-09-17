"""Unit tests for the seeded ``GraphComposer`` fragment-composition engine."""

from __future__ import annotations

import re
from pathlib import Path
from random import Random
from typing import Any, get_args

import pytest

from app.cloudforge.errors import GraphIntegrityError
from app.cloudforge.generate.base import ScenarioBundle
from app.cloudforge.generate.composer import ComposerGenerator, GraphComposer, _pick
from app.cloudforge.generate.composer_ids import retoken
from app.cloudforge.generate.composer_kinds import (
    AWS_KINDS,
    AZURE_KINDS,
    CORE_KINDS,
    EXTRA_ROLES,
    GCP_KINDS,
    K8S_KINDS,
    POOLS,
    SHORT,
    kinds_for,
)
from app.cloudforge.generate.fragments.base import get_fragment
from app.cloudforge.io.loaders import load_yaml
from app.cloudforge.models.graph import NodeType
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
    """Two fragments sharing a namespace collide on their fixed core slugs."""
    composer = GraphComposer(_spec(), seed=0)
    plan = [("core.ci_cd_iam_chain", "dup", {"path_hops": 3})] * 2
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
    assert [n for n in g.nodes if n.origin == "decoy"] == []


def _origin_counts(spec: ScenarioSpec, seed: int) -> dict[str, int]:
    g = GraphComposer(spec, seed=seed).generate().graph
    counts: dict[str, int] = {}
    for n in g.nodes:
        counts[n.origin or "?"] = counts.get(n.origin or "?", 0) + 1
    return counts


def test_easy_difficulty_yields_fewer_extras_than_hard() -> None:
    """Same spec, same seed: easy must always under-shoot hard on every extra kind.

    ``decoy.iam_role_dead_end`` mints 2 nodes per instance (role + policy),
    ``false_positive.public_denied_bucket`` mints 1, ``compensating_control.explicit_deny``
    mints 3 (bucket + trail + the data set it guards) -- so a decoy count of 1 vs 3
    shows up as 2 vs 6 nodes, not 1 vs 3.
    """
    for seed in (1, 7, 17):
        easy = _origin_counts(_spec(scale_profile="small", difficulty="easy"), seed)
        hard = _origin_counts(_spec(scale_profile="small", difficulty="hard"), seed)
        assert easy.get("decoy", 0) == 2  # 1 instance
        assert easy.get("false_positive", 0) == 0
        assert easy.get("compensating_control", 0) == 0
        assert hard.get("decoy", 0) == 6  # 3 instances
        assert hard.get("false_positive", 0) == 2  # 2 instances
        assert hard.get("compensating_control", 0) in (3, 6)  # 1..2 instances
        assert easy.get("decoy", 0) < hard.get("decoy", 0)
        assert easy.get("false_positive", 0) < hard.get("false_positive", 0)


def test_difficulty_biases_the_noise_fill_toward_the_profile_ends() -> None:
    """Easy stays near ``min_nodes``; hard stays near ``max_nodes``, over many seeds."""
    easy_spec = _spec(scale_profile="medium", difficulty="easy")
    hard_spec = _spec(scale_profile="medium", difficulty="hard")
    easy_sizes = [len(GraphComposer(easy_spec, seed=s).generate().graph.nodes) for s in range(20)]
    hard_sizes = [len(GraphComposer(hard_spec, seed=s).generate().graph.nodes) for s in range(20)]
    assert sum(easy_sizes) / len(easy_sizes) < sum(hard_sizes) / len(hard_sizes)


def test_variation_axes_override_wins_over_difficulty() -> None:
    """A hard spec would otherwise mint 3 decoys; an explicit override still wins."""
    spec = _spec(scale_profile="small", difficulty="hard", variation_axes={"decoy": "0"})
    g = GraphComposer(spec, seed=1).generate().graph
    assert [n for n in g.nodes if n.origin == "decoy"] == []


def test_difficulty_is_deterministic_per_spec_and_seed() -> None:
    for difficulty in ("easy", "medium", "hard"):
        spec = _spec(scale_profile="small", difficulty=difficulty)
        a = GraphComposer(spec, seed=5).generate()
        b = GraphComposer(spec, seed=5).generate()
        assert a.graph.model_dump(by_alias=True) == b.graph.model_dump(by_alias=True)


def test_stays_within_max_nodes_for_tiny_profile() -> None:
    """The mandatory extras must not push a tight profile past its ``max_nodes``."""
    g = GraphComposer(_spec(scale_profile="tiny"), seed=1).generate().graph
    assert 10 <= len(g.nodes) <= 20


def test_unknown_scenario_type_falls_back_to_ci_cd_core() -> None:
    spec = _spec(scenario_type="unmapped_family", scale_profile="small")
    bundle = GraphComposer(spec, seed=1).generate()
    core = [n for n in bundle.graph.nodes if n.origin == "core"]
    assert any(n.id.endswith("/cicd-github") for n in core)


def test_seed_salting_produces_unique_namespaces() -> None:
    spec = _spec(scale_profile="small")
    b0 = GraphComposer(spec, seed=0).generate()
    b1 = GraphComposer(spec, seed=1).generate()
    b2 = GraphComposer(spec, seed=2).generate()
    ids0 = {n.id for n in b0.graph.nodes}
    ids1 = {n.id for n in b1.graph.nodes}
    ids2 = {n.id for n in b2.graph.nodes}
    assert all(_UNSALTED_NS.match(nid) for nid in ids0)
    assert all(_SALTED_NS.match(nid) for nid in ids1)
    assert all(_SALTED_NS.match(nid) for nid in ids2)
    assert ids1.isdisjoint(ids2)


_UNSALTED_NS = re.compile(r"^n\d{2,}/")
_SALTED_NS = re.compile(r"^n\d{2,}_[0-9a-f]{4}/")
_ROLE_WORDS = re.compile(r"core0_|decoy|noise|false_positive|fp0_|ctrl0_|honeypot|compensat", re.I)


def _namespace_of(node_id: str) -> str:
    return node_id.split("/", 1)[0]


def test_namespaces_and_names_carry_no_role_words() -> None:
    for seed in (0, 1, 17):
        g = GraphComposer(_spec(scale_profile="small"), seed=seed).generate().graph
        for n in g.nodes:
            assert not _ROLE_WORDS.search(n.id), n.id
            assert not _ROLE_WORDS.search(n.name), n.name


def test_seed_zero_tokens_are_unique_per_node_and_unsalted() -> None:
    g = GraphComposer(_spec(scale_profile="small"), seed=0).generate().graph
    tokens = [_namespace_of(n.id) for n in g.nodes]
    assert len(set(tokens)) == len(g.nodes)
    assert all(_UNSALTED_NS.match(f"{token}/") for token in tokens)


def test_every_node_has_its_own_token() -> None:
    """Tokens are per node, so sorting ids by token exposes no fragment cluster."""
    for seed in (1, 17):
        g = GraphComposer(_spec(scale_profile="small"), seed=seed).generate().graph
        tokens = [_namespace_of(n.id) for n in g.nodes]
        assert len(set(tokens)) == len(g.nodes), seed


def test_true_path_nodes_do_not_share_a_token() -> None:
    for seed in (1, 17):
        bundle = GraphComposer(_spec(scale_profile="small"), seed=seed).generate()
        for path in bundle.ground_truth.paths:
            tokens = [_namespace_of(nid) for nid in path.nodes]
            assert len(set(tokens)) == len(path.nodes), (seed, path.id)


def test_retoken_rewrites_every_reference_through_one_map() -> None:
    bundle = GraphComposer(_spec(scale_profile="small"), seed=17).generate()
    ids = {n.id for n in bundle.graph.nodes}
    edge_keys = {e.key for e in bundle.graph.edges}
    assert all(e.from_ in ids and e.to in ids for e in bundle.graph.edges)
    for path in bundle.ground_truth.paths:
        assert set(path.nodes) <= ids and set(path.edges) <= edge_keys
    for finding in bundle.findings.findings:
        assert set(finding.resource_ids) <= ids


def test_retoken_rejects_a_dangling_reference() -> None:
    part = get_fragment("decoy.iam_role_dead_end").build("f0", Random(0), {})
    part.findings[0].resource_ids.append("f0/never-built")
    with pytest.raises(GraphIntegrityError):
        retoken(part, seed=1, salt="abcd")


def test_origin_is_stamped_from_the_fragment_kind() -> None:
    bundle = GraphComposer(_spec(scale_profile="small"), seed=1).generate()
    origins = {n.origin for n in bundle.graph.nodes}
    assert None not in origins
    assert {"core", "decoy", "noise", "false_positive", "compensating_control"} <= origins
    path_nodes = {nid for p in bundle.ground_truth.paths for nid in p.nodes}
    assert all(n.origin == "core" for n in bundle.graph.nodes if n.id in path_nodes)


def test_names_are_unique_per_node_type() -> None:
    for seed in (0, 5, 17):
        g = GraphComposer(_spec(scale_profile="small"), seed=seed).generate().graph
        keys = [(n.type.value, n.name) for n in g.nodes]
        assert len(keys) == len(set(keys)), seed


# --- vendor pools --------------------------------------------------------------

_CLOUDS = get_args(ScenarioSpec.model_fields["cloud"].annotation)
_VENDOR_EXAMPLES = {
    "azure": "examples/azure_imds_keyvault_harvest.yaml",
    "gcp": "examples/gcp_workload_identity_federation.yaml",
    "k8s": "examples/k8s_pod_irsa_exfil.yaml",
}


def _vendor_spec(cloud: str, **over: Any) -> ScenarioSpec:
    data = load_yaml(Path(_VENDOR_EXAMPLES[cloud]))
    data.update(over)
    return ScenarioSpec.model_validate(data)


def _plan_kinds(spec: ScenarioSpec, seed: int) -> list[str]:
    composer = GraphComposer(spec, seed=seed)
    return [kind for kind, _ns, _params in composer._plan(Random(seed))]  # type: ignore[attr-defined]


@pytest.mark.parametrize("cloud", _CLOUDS)
def test_every_cloud_value_has_a_pool_with_every_role(cloud: str) -> None:
    assert cloud in POOLS
    assert len(kinds_for(cloud, "noise")) >= 4
    for role in EXTRA_ROLES:
        assert kinds_for(cloud, role), (cloud, role)
    assert set(POOLS[cloud]) <= set(SHORT)


def test_pools_are_the_vendor_sets_the_design_names() -> None:
    assert POOLS["aws"] == AWS_KINDS
    assert POOLS["azure"] == AZURE_KINDS
    assert POOLS["gcp"] == GCP_KINDS
    assert POOLS["k8s"] == K8S_KINDS + AWS_KINDS
    assert set(POOLS["multi_cloud"]) == set(AWS_KINDS + AZURE_KINDS + GCP_KINDS + K8S_KINDS)


@pytest.mark.parametrize("cloud", ["azure", "gcp"])
def test_azure_and_gcp_plans_draw_every_non_core_kind_from_their_own_pool(cloud: str) -> None:
    for seed in (0, 1, 17):
        kinds = _plan_kinds(_vendor_spec(cloud, scale_profile="small"), seed)
        assert kinds[0] == CORE_KINDS[_vendor_spec(cloud).scenario_type]
        assert set(kinds[1:]) <= set(POOLS[cloud]), (cloud, seed)


def test_k8s_plan_draws_from_both_the_k8s_and_the_aws_pool() -> None:
    kinds = set()
    for seed in (0, 1, 17):
        kinds |= set(_plan_kinds(_vendor_spec("k8s", scale_profile="small"), seed)[1:])
    assert kinds <= set(POOLS["k8s"])
    assert kinds & set(K8S_KINDS)
    assert kinds & set(AWS_KINDS)


def test_aws_plan_never_draws_a_vendor_kind() -> None:
    for seed in (0, 1, 17):
        kinds = _plan_kinds(_spec(scale_profile="small"), seed)
        assert set(kinds[1:]) <= set(AWS_KINDS), seed


@pytest.mark.parametrize("cloud", ["azure", "gcp", "k8s"])
def test_vendor_estates_mint_only_their_vendor_types_outside_the_core(cloud: str) -> None:
    """Every non-core node an Azure or GCP estate carries is that vendor's own type
    or a data set one of them holds; a Kubernetes estate may add AWS types, since
    its path federates into AWS."""
    for seed in (0, 17):
        g = GraphComposer(_vendor_spec(cloud, scale_profile="small"), seed=seed).generate().graph
        for n in g.nodes:
            if n.origin == "core" or n.type is NodeType.DATASET:
                continue
            value = n.type.value
            if cloud == "azure":
                assert value.startswith("Azure"), (seed, n.id, value)
            elif cloud == "gcp":
                assert value.startswith("Gcp"), (seed, n.id, value)
            else:
                assert not value.startswith(("Azure", "Gcp")), (seed, n.id, value)


@pytest.mark.parametrize("cloud", ["azure", "gcp", "k8s"])
def test_variation_axes_count_instances_per_role_whatever_the_vendor(cloud: str) -> None:
    axes = {"decoy": "2", "fp": "1", "ctrl": "1"}
    for seed in (0, 5):
        kinds = _plan_kinds(_vendor_spec(cloud, scale_profile="small", variation_axes=axes), seed)
        roles = [SHORT[k] for k in kinds]
        assert roles.count("decoy") == 2, (cloud, seed, kinds)
        assert roles.count("fp") == 1, (cloud, seed, kinds)
        assert roles.count("ctrl") == 1, (cloud, seed, kinds)


@pytest.mark.parametrize("cloud", ["azure", "gcp", "k8s"])
def test_vendor_origin_counts_respond_to_difficulty(cloud: str) -> None:
    for seed in (1, 7, 17):
        easy = _origin_counts(_vendor_spec(cloud, scale_profile="small", difficulty="easy"), seed)
        hard = _origin_counts(_vendor_spec(cloud, scale_profile="small", difficulty="hard"), seed)
        assert easy.get("false_positive", 0) == 0
        assert easy.get("compensating_control", 0) == 0
        assert 0 < easy.get("decoy", 0) < hard.get("decoy", 0), (cloud, seed)
        assert hard.get("false_positive", 0) > 0, (cloud, seed)
        assert hard.get("compensating_control", 0) > 0, (cloud, seed)


@pytest.mark.parametrize("cloud", ["azure", "gcp", "k8s"])
def test_vendor_estates_are_deterministic_per_spec_and_seed(cloud: str) -> None:
    spec = _vendor_spec(cloud, scale_profile="small")
    for seed in (0, 17):
        a = GraphComposer(spec, seed=seed).generate()
        b = GraphComposer(spec, seed=seed).generate()
        assert a.graph.model_dump(by_alias=True) == b.graph.model_dump(by_alias=True)
        assert a.findings.model_dump() == b.findings.model_dump()
        assert a.ground_truth.model_dump() == b.ground_truth.model_dump()


@pytest.mark.parametrize("cloud", ["aws", "azure", "gcp", "k8s"])
@pytest.mark.parametrize("profile", ["tiny", "small"])
def test_multi_node_kinds_never_overshoot_the_profile_band(profile: str, cloud: str) -> None:
    """Noise kinds may mint two nodes (a namespace with its pod, a bucket with its
    data set) and a control mints three; both the fill and the extras must count a
    kind's real size instead of assuming one or two nodes per kind."""
    lo, hi = {"tiny": (10, 20), "small": (25, 50)}[profile]
    for seed in range(25):
        spec = (
            _spec(scale_profile=profile)
            if cloud == "aws"
            else _vendor_spec(cloud, scale_profile=profile)
        )
        g = GraphComposer(spec, seed=seed).generate().graph
        assert lo <= len(g.nodes) <= hi, (cloud, profile, seed, len(g.nodes))


def test_picking_from_a_one_kind_pool_spends_no_rng_draw() -> None:
    """A single-kind role (every role in the AWS pool) keeps the plan's draw order."""
    rng = Random(3)
    state = rng.getstate()
    assert _pick(rng, ("only",)) == "only"
    assert rng.getstate() == state
    _pick(rng, ("a", "b"))
    assert rng.getstate() != state


@pytest.mark.parametrize("cloud", ["azure", "gcp", "k8s"])
def test_vendor_estate_ids_and_names_carry_no_role_words(cloud: str) -> None:
    for seed in (0, 1, 17):
        g = GraphComposer(_vendor_spec(cloud, scale_profile="small"), seed=seed).generate().graph
        for n in g.nodes:
            assert not _ROLE_WORDS.search(n.id), n.id
            assert not _ROLE_WORDS.search(n.name), n.name
        keys = [(n.type.value, n.name) for n in g.nodes]
        assert len(keys) == len(set(keys)), (cloud, seed)
