"""Grading: the entry-hop-target rule, coverage, full path, extras, old keys.

``cloudforge grade`` used to call a path a hit when the guess was an ordered
subsequence of it, so two correct cards on a ten-node path passed. Now a hit
needs the entry, the access-granting hop and the target in the guess, in that
order; the other nodes are optional and reported as coverage; the whole path in
order is ``full_path``; wrong nodes are extras. A key without ``hop`` or
``target`` falls back to the second and the last node.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.cloudforge.generate.composer import GraphComposer
from app.cloudforge.io.loaders import load_yaml
from app.cloudforge.lab.grade import grade_submission
from app.cloudforge.lab.pack import _grade_key
from app.cloudforge.lab.submission import LabSubmission, PathGuess
from app.cloudforge.models.hops import access_hop, positional_hop
from app.cloudforge.models.scenario import ScenarioSpec

_KEY = {
    "paths": [
        {
            "id": "p1",
            "nodes": ["entry", "hop", "mid1", "mid2", "sink"],
            "hop": "hop",
            "target": "sink",
            "sink_kind": "data",
        }
    ],
    "finding_families": ["iam_passrole_risk", "s3_logging_missing"],
}
_EXAMPLES = sorted(Path("examples").glob("*.yaml"))
_TWO_OF_FIVE = 0.4
_TRIPLE = 3


def _grade(*nodes: str, findings: list[str] | None = None):  # type: ignore[no-untyped-def]
    guess = LabSubmission(paths=[PathGuess(nodes=list(nodes))], findings=findings or [])
    return grade_submission(_KEY, guess)


def test_the_triple_in_order_hits() -> None:
    result = _grade("entry", "hop", "sink", findings=["iam_passrole_risk"])
    assert result.path_hits == ["p1"]
    assert result.path_misses == []
    assert result.finding_hits == ["iam_passrole_risk"]
    assert result.finding_misses == ["s3_logging_missing"]
    score = result.path_scores[0]
    assert score.hit and not score.full_path
    assert (score.found, score.total, score.coverage) == (3, 5, 0.6)


@pytest.mark.parametrize("length", [2, 3, 4, 8, 12])
def test_the_triple_hits_at_every_path_length(length: int) -> None:
    nodes = [f"n{i}" for i in range(length)]
    hop = positional_hop(nodes)
    key = {"paths": [{"id": "p", "nodes": nodes, "hop": hop, "target": nodes[-1]}]}
    triple = list(dict.fromkeys([nodes[0], hop, nodes[-1]]))
    result = grade_submission(key, LabSubmission(paths=[PathGuess(nodes=triple)]))
    assert result.path_hits == ["p"]


def test_entry_plus_sink_alone_misses() -> None:
    result = _grade("entry", "sink")
    assert result.path_hits == []
    assert result.path_misses == ["p1"]
    assert result.path_scores[0].coverage == _TWO_OF_FIVE


def test_the_full_path_hits_with_full_path_true() -> None:
    result = _grade("entry", "hop", "mid1", "mid2", "sink")
    assert result.path_hits == ["p1"]
    score = result.path_scores[0]
    assert score.full_path and score.coverage == 1.0
    assert result.extras == []


def test_a_wrong_hop_misses_and_is_an_extra() -> None:
    result = _grade("entry", "wrong", "sink")
    assert result.path_misses == ["p1"]
    assert result.extras == ["wrong"]


def test_the_triple_out_of_order_misses() -> None:
    result = _grade("hop", "entry", "sink")
    assert result.path_misses == ["p1"]


def test_a_wrong_node_inside_a_hit_still_counts_as_an_extra() -> None:
    result = _grade("entry", "wrong", "hop", "sink")
    assert result.path_hits == ["p1"]
    assert result.extras == ["wrong"]


def test_the_best_guess_grades_the_path() -> None:
    guess = LabSubmission(
        paths=[PathGuess(nodes=["entry", "sink"]), PathGuess(nodes=["entry", "hop", "sink"])]
    )
    result = grade_submission(_KEY, guess)
    assert result.path_hits == ["p1"]
    assert result.path_scores[0].found == _TRIPLE


def test_wrong_findings_are_extras() -> None:
    result = _grade("entry", "hop", "sink", findings=["not_a_family"])
    assert "not_a_family" in result.extras


def test_empty_submission_misses_everything() -> None:
    result = grade_submission(_KEY, LabSubmission())
    assert result.path_misses == ["p1"]
    assert set(result.finding_misses) == {"iam_passrole_risk", "s3_logging_missing"}
    assert result.path_scores[0].coverage == 0.0


def _hits(key: dict[str, object], *nodes: str) -> list[str]:
    return grade_submission(key, LabSubmission(paths=[PathGuess(nodes=list(nodes))])).path_hits


def test_an_old_key_without_hop_or_target_uses_the_second_and_last_node() -> None:
    key: dict[str, object] = {
        "paths": [{"id": "p1", "nodes": ["a", "b", "c", "d"]}],
        "finding_families": [],
    }
    assert _hits(key, "a", "b", "d") == ["p1"]
    assert _hits(key, "a", "c", "d") == []
    two: dict[str, object] = {"paths": [{"id": "p2", "nodes": ["a", "b"]}]}
    assert _hits(two, "a", "b") == ["p2"]


@pytest.mark.parametrize("difficulty", ["easy", "medium", "hard"])
@pytest.mark.parametrize("example", _EXAMPLES, ids=[e.stem for e in _EXAMPLES])
def test_the_old_key_fallback_picks_the_type_aware_hop_on_every_example(
    example: Path, difficulty: str
) -> None:
    """A key stripped of ``hop`` must grade the same path the type-aware rule
    would: on every family the second node is that hop."""
    data = load_yaml(example)
    data["difficulty"] = difficulty
    spec = ScenarioSpec.model_validate(data)
    for seed in (0, 17):
        bundle = GraphComposer(spec, seed=seed).generate()
        types = {n.id: n.type for n in bundle.graph.nodes}
        key = _grade_key(bundle)
        entries = key["paths"]
        assert isinstance(entries, list)
        stripped: dict[str, object] = {
            "paths": [{"id": e["id"], "nodes": e["nodes"]} for e in entries],
            "finding_families": key["finding_families"],
        }
        for entry in entries:
            nodes = list(entry["nodes"])
            assert entry["hop"] == access_hop(nodes, types) == positional_hop(nodes)
            triple = list(dict.fromkeys([nodes[0], entry["hop"], entry["target"]]))
            assert entry["id"] in _hits(stripped, *triple), (example.stem, difficulty, seed)
