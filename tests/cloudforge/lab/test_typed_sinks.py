"""Every family declares what the attacker reaches, and the packs carry it.

Before this, every labeled path ended at a ``DataSet`` in the storage zone, so
the ending was the same card in every lab. Now each core fragment declares a
``sink_kind`` and a ``target``: for every example the target is the last node of
the primary path and has the type the kind names, several kinds exist across
the fifteen families, the grade key carries both fields, and a key written
before the fields existed still grades.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.cloudforge.errors import GraphIntegrityError
from app.cloudforge.generate.composer import GraphComposer, _assert_sinks_declared
from app.cloudforge.io.loaders import load_yaml
from app.cloudforge.lab.grade import grade_submission
from app.cloudforge.lab.pack import LabRequest, write_lab
from app.cloudforge.lab.paths import LabPaths
from app.cloudforge.lab.submission import LabSubmission, PathGuess
from app.cloudforge.models.findings import SINK_NODE_TYPES, GroundTruthPath, SinkKind
from app.cloudforge.models.graph import GraphNode, NodeSecurity, NodeTags, NodeType
from app.cloudforge.models.scenario import ScenarioSpec

_EXAMPLES = sorted(Path("examples").glob("*.yaml"))
_MIN_DISTINCT_KINDS = 3
# The endings the brief assigns per family.
_EXPECTED_KINDS = {
    "iam_privesc_policy_version": SinkKind.ROLE,
    "secretsmanager_policy_overbroad": SinkKind.SECRET,
    "kms_key_overbroad": SinkKind.KEY,
    "ecr_repository_public_read": SinkKind.IMAGE,
    "sqs_queue_overbroad_policy": SinkKind.QUEUE,
    "cross_account_trust": SinkKind.ROLE,
    "public_ebs_snapshot": SinkKind.SNAPSHOT,
    "public_rds_instance": SinkKind.DATABASE,
}


def _bundle(example: Path, seed: int = 0):  # type: ignore[no-untyped-def]
    spec = ScenarioSpec.model_validate(load_yaml(example))
    return GraphComposer(spec, seed=seed).generate()


@pytest.mark.parametrize("example", _EXAMPLES, ids=[e.stem for e in _EXAMPLES])
def test_target_is_the_last_node_and_has_the_declared_type(example: Path) -> None:
    for seed in (0, 17):
        bundle = _bundle(example, seed)
        types = {n.id: n.type for n in bundle.graph.nodes}
        primary = bundle.ground_truth.paths[0]
        assert primary.target == primary.nodes[-1]
        assert types[primary.target] in SINK_NODE_TYPES[primary.sink_kind], primary.sink_kind
        for path in bundle.ground_truth.paths[1:]:
            assert path.target == path.nodes[-1]
            assert types[path.target] in SINK_NODE_TYPES[path.sink_kind], path.id


@pytest.mark.parametrize("example", _EXAMPLES, ids=[e.stem for e in _EXAMPLES])
def test_family_ends_where_the_brief_says(example: Path) -> None:
    primary = _bundle(example).ground_truth.paths[0]
    assert primary.sink_kind is _EXPECTED_KINDS.get(example.stem, SinkKind.DATA)


def test_at_least_three_distinct_sink_kinds_across_the_families() -> None:
    kinds = {_bundle(e).ground_truth.paths[0].sink_kind for e in _EXAMPLES}
    assert len(kinds) >= _MIN_DISTINCT_KINDS, kinds


def test_grade_key_round_trips_sink_kind_and_target(tmp_path: Path) -> None:
    spec = ScenarioSpec.model_validate(load_yaml(Path("examples/kms_key_overbroad.yaml")))
    out = LabPaths.from_dir(tmp_path / "lab")
    bundle = write_lab(LabRequest(spec=spec, seed=17), out)
    key = json.loads(out.grade_key.read_text(encoding="utf-8"))
    by_id = {p.id: p for p in bundle.ground_truth.paths}
    for entry in key["paths"]:
        path = by_id[entry["id"]]
        assert entry["sink_kind"] == path.sink_kind.value == "key"
        assert entry["target"] == path.target == entry["nodes"][-1]
    # The instructor's ground truth loads back with the same fields.
    truth = json.loads((out.instructor / "ground_truth_paths.json").read_text(encoding="utf-8"))
    for item in truth["paths"]:
        loaded = GroundTruthPath.model_validate(item)
        assert loaded.sink_kind is by_id[loaded.id].sink_kind
        assert loaded.target == by_id[loaded.id].target


def test_a_key_without_the_new_fields_still_grades() -> None:
    old_key = {
        "paths": [{"id": "p1", "nodes": ["a", "b", "c"]}],
        "finding_families": ["s3_public_exposure"],
    }
    result = grade_submission(old_key, LabSubmission(paths=[PathGuess(nodes=["a", "b", "c"])]))
    assert result.path_hits == ["p1"]


def test_a_path_without_target_loads_with_the_last_node_as_data_sink() -> None:
    path = GroundTruthPath.model_validate(
        {"id": "p", "severity": "high", "nodes": ["x", "y"], "edges": [], "explanation": "old"}
    )
    assert path.sink_kind is SinkKind.DATA
    assert path.target == "y"


def _role(node_id: str) -> GraphNode:
    return GraphNode(
        id=node_id,
        type=NodeType.IAM_ROLE,
        name=node_id,
        tags=NodeTags(env="prod", owner="t", app="t"),
        security=NodeSecurity(criticality="high"),
    )


def _path(target: str, kind: SinkKind) -> GroundTruthPath:
    return GroundTruthPath(
        id="p",
        severity="critical",
        nodes=["a", "b"],
        edges=[],
        sink_kind=kind,
        target=target,
        explanation="t",
    )


def test_composer_rejects_a_target_that_is_not_the_last_node() -> None:
    with pytest.raises(GraphIntegrityError):
        _assert_sinks_declared([_role("a"), _role("b")], [_path("a", SinkKind.ROLE)])


def test_composer_rejects_a_target_whose_type_does_not_match_the_kind() -> None:
    with pytest.raises(GraphIntegrityError):
        _assert_sinks_declared([_role("a"), _role("b")], [_path("b", SinkKind.DATA)])
    _assert_sinks_declared([_role("a"), _role("b")], [_path("b", SinkKind.ROLE)])
