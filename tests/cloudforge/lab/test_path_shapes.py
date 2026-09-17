"""Difficulty shapes the path, not only the scenery.

Before this every family had a fixed path length and only the CI chain drew
its hops. Now the composer draws the shape per ``(spec, seed)`` inside a band
set by difficulty: intermediate identity hops for the identity-chain families
(easy 0, medium 0..3, hard 2..6), an identity route next to the public one for
the resource-shaped families, a dead-end branch from the entry (hard always,
medium half the time, easy never) and, on hard, a blocked lookalike of the
exposed resource. These tests read the composed bundles for every example and
hold the shape to that contract: hard lengths vary, easy is the minimum, medium
sits between, hard branches, lookalikes exist, nothing in an id or name says
what a node is for, the profile still bounds the estate (a clamp is recorded),
and the true path grades as a hit at every length.
"""

from __future__ import annotations

import re
from collections import deque
from pathlib import Path
from statistics import mean

import pytest

from app.cloudforge.generate.base import ScenarioBundle
from app.cloudforge.generate.composer import GraphComposer
from app.cloudforge.generate.scale_profiles import get_profile
from app.cloudforge.io.loaders import load_yaml
from app.cloudforge.lab.grade import grade_submission
from app.cloudforge.lab.pack import _grade_key
from app.cloudforge.lab.submission import LabSubmission, PathGuess
from app.cloudforge.models.graph import NodeType
from app.cloudforge.models.scenario import ScenarioSpec
from app.cloudforge.report.sections import build_critical_path

_EXAMPLES = sorted(Path("examples").glob("*.yaml"))
_IDS = [e.stem for e in _EXAMPLES]
_IDENTITY_FAMILIES = {
    "ci_cd_iam_chain",
    "cross_account_trust",
    "iam_privesc_policy_version",
    "ec2_imds_credential_exfil",
    "lambda_public_function_url",
    "k8s_pod_irsa_exfil",
    "azure_imds_keyvault_harvest",
    "gcp_workload_identity_federation",
}
# Resource-shaped family -> the node type of its exposed resource.
_EXPOSED_TYPES = {
    "public_data_exposure": NodeType.S3_BUCKET,
    "kms_key_overbroad": NodeType.KMS_KEY,
    "public_ebs_snapshot": NodeType.EBS_SNAPSHOT,
    "public_rds_instance": NodeType.RDS_INSTANCE,
    "secretsmanager_policy_overbroad": NodeType.SECRETS_MANAGER_SECRET,
    "ecr_repository_public_read": NodeType.ECR_REPOSITORY,
    "sqs_queue_overbroad_policy": NodeType.SQS_QUEUE,
}
_SEEDS = range(20)
_MIN_DISTINCT_HARD_LENGTHS = 3
_MIN_HARD_SPAN = 4
_TWO_OF_THE_TYPE = 2
_SHAPE_WORDS = re.compile(r"hop|intermediate|twin|dead|lookalike|route|prefix", re.IGNORECASE)
_CACHE: dict[tuple[str, str, int, str], ScenarioBundle] = {}


def _bundle(example: Path, difficulty: str, seed: int, profile: str = "small") -> ScenarioBundle:
    key = (example.stem, difficulty, seed, profile)
    if key not in _CACHE:
        data = load_yaml(example)
        data["difficulty"] = difficulty
        data["scale_profile"] = profile
        _CACHE[key] = GraphComposer(ScenarioSpec.model_validate(data), seed=seed).generate()
    return _CACHE[key]


def _length(bundle: ScenarioBundle) -> int:
    return len(bundle.ground_truth.paths[0].nodes)


def _lengths(example: Path, difficulty: str) -> list[int]:
    return [_length(_bundle(example, difficulty, seed)) for seed in _SEEDS]


def _reachable_off_path(bundle: ScenarioBundle) -> set[str]:
    """Node ids reachable from the primary path's entry that no path names."""
    primary = bundle.ground_truth.paths[0]
    on_path = {nid for path in bundle.ground_truth.paths for nid in path.nodes}
    forward: dict[str, list[str]] = {}
    for edge in bundle.graph.edges:
        forward.setdefault(edge.from_, []).append(edge.to)
    seen, queue = {primary.nodes[0]}, deque([primary.nodes[0]])
    while queue:
        node = queue.popleft()
        for nxt in forward.get(node, []):
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return seen - on_path


@pytest.mark.parametrize("example", _EXAMPLES, ids=_IDS)
def test_hard_lengths_vary_for_identity_families(example: Path) -> None:
    if example.stem not in _IDENTITY_FAMILIES:
        pytest.skip("resource-shaped family: its primary path stays short by nature")
    lengths = set(_lengths(example, "hard"))
    assert len(lengths) >= _MIN_DISTINCT_HARD_LENGTHS, lengths
    assert max(lengths) - min(lengths) >= _MIN_HARD_SPAN, lengths


@pytest.mark.parametrize("example", _EXAMPLES, ids=_IDS)
def test_easy_is_always_the_family_minimum(example: Path) -> None:
    easy = _lengths(example, "easy")
    floor = min(easy + _lengths(example, "medium") + _lengths(example, "hard"))
    assert set(easy) == {floor}, easy


@pytest.mark.parametrize("example", _EXAMPLES, ids=_IDS)
def test_medium_sits_between_easy_and_hard(example: Path) -> None:
    easy, medium, hard = (_lengths(example, d) for d in ("easy", "medium", "hard"))
    assert min(easy) <= min(medium) <= max(medium) <= max(hard)
    if example.stem in _IDENTITY_FAMILIES:
        assert mean(easy) < mean(medium) < mean(hard)


@pytest.mark.parametrize("example", _EXAMPLES, ids=_IDS)
def test_hard_estates_branch_from_the_entry(example: Path) -> None:
    """Walking forward from the entry alone must not solve a hard lab: something
    reachable from it is not on any path, and more of it than on easy."""
    for seed in (0, 17):
        hard = _reachable_off_path(_bundle(example, "hard", seed))
        assert hard, (example.stem, seed)
        assert len(hard) > len(_reachable_off_path(_bundle(example, "easy", seed)))


@pytest.mark.parametrize("example", _EXAMPLES, ids=_IDS)
def test_hard_resource_families_carry_a_blocked_lookalike(example: Path) -> None:
    exposed = _EXPOSED_TYPES.get(example.stem)
    if exposed is None:
        pytest.skip("identity family")
    for seed in (0, 17):
        bundle = _bundle(example, "hard", seed)
        on_path = {nid for path in bundle.ground_truth.paths for nid in path.nodes}
        core = [n for n in bundle.graph.nodes if n.type is exposed and n.origin == "core"]
        twins = [n for n in core if n.id not in on_path and "compensating_control" in n.attributes]
        assert len(core) >= _TWO_OF_THE_TYPE, (example.stem, seed)
        assert twins, (example.stem, seed)
        assert any(n.id in on_path for n in core)


@pytest.mark.parametrize("example", _EXAMPLES, ids=_IDS)
def test_medium_and_hard_resource_families_may_add_an_identity_route(example: Path) -> None:
    """The second, high-severity path reaches the same sink as the public one and
    starts at an application role or the CI identity in front of it."""
    if example.stem not in _EXPOSED_TYPES:
        pytest.skip("identity family")
    seen_route = False
    for seed in _SEEDS:
        bundle = _bundle(example, "hard", seed)
        primary, *others = bundle.ground_truth.paths
        for route in others:
            seen_route = True
            assert route.target == primary.target
            assert route.severity == "high"
            types = {n.id: n.type for n in bundle.graph.nodes}
            assert types[route.nodes[0]] in (NodeType.IAM_ROLE, NodeType.CICD_IDENTITY)
    assert seen_route, example.stem
    for seed in _SEEDS:
        assert len(_bundle(example, "easy", seed).ground_truth.paths) == 1


@pytest.mark.parametrize("difficulty", ["easy", "medium", "hard"])
@pytest.mark.parametrize("example", _EXAMPLES, ids=_IDS)
def test_no_id_or_name_says_what_a_node_is_for(example: Path, difficulty: str) -> None:
    for seed in (0, 17):
        for node in _bundle(example, difficulty, seed).graph.nodes:
            assert not _SHAPE_WORDS.search(node.id), node.id
            assert not _SHAPE_WORDS.search(node.name), node.name


@pytest.mark.parametrize("difficulty", ["easy", "medium", "hard"])
@pytest.mark.parametrize("example", _EXAMPLES, ids=_IDS)
def test_shape_is_deterministic_per_spec_and_seed(example: Path, difficulty: str) -> None:
    data = load_yaml(example)
    data["difficulty"] = difficulty
    data["scale_profile"] = "small"
    spec = ScenarioSpec.model_validate(data)
    a = GraphComposer(spec, seed=17).generate()
    b = GraphComposer(spec, seed=17).generate()
    assert a.graph.model_dump(by_alias=True) == b.graph.model_dump(by_alias=True)
    assert a.ground_truth.model_dump() == b.ground_truth.model_dump()


@pytest.mark.parametrize("example", _EXAMPLES, ids=_IDS)
def test_the_profile_still_bounds_the_estate_and_a_clamp_is_recorded(example: Path) -> None:
    hi = get_profile("tiny").max_nodes
    clamped = 0
    for seed in range(8):
        bundle = _bundle(example, "hard", seed, profile="tiny")
        assert len(bundle.graph.nodes) <= hi, (example.stem, seed)
        if bundle.ground_truth.notes:
            clamped += 1
            assert "clamped" in bundle.ground_truth.notes[0]
            assert bundle.ground_truth.notes[0] in build_critical_path(bundle)
    if example.stem == "ci_cd_iam_chain":
        assert clamped, "a hard CI chain does not fit the tiny profile at every seed"


@pytest.mark.parametrize("example", _EXAMPLES, ids=_IDS)
def test_variation_axes_still_win_over_the_difficulty_extras(example: Path) -> None:
    data = load_yaml(example)
    data["difficulty"] = "hard"
    data["scale_profile"] = "small"
    data["variation_axes"] = {"decoy": "0", "fp": "0"}
    bundle = GraphComposer(ScenarioSpec.model_validate(data), seed=3).generate()
    assert not [n for n in bundle.graph.nodes if n.origin in ("decoy", "false_positive")]
    assert bundle.ground_truth.paths


@pytest.mark.parametrize("example", _EXAMPLES, ids=_IDS)
def test_the_true_path_grades_as_a_hit_at_every_length(example: Path) -> None:
    for seed in _SEEDS:
        bundle = _bundle(example, "hard", seed)
        key = _grade_key(bundle)
        for path in bundle.ground_truth.paths:
            guess = LabSubmission(paths=[PathGuess(nodes=list(path.nodes))])
            assert path.id in grade_submission(key, guess).path_hits, (seed, path.id)
