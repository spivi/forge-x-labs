"""The student tree must not reveal which nodes are the path, decoys, or noise.

Node ids are the join key between ``student/estate.json`` and every instructor
artifact, so they are minted once by the composer for both trees. These tests
write a real lab for every example spec at two seeds and check, from the files a
student actually receives, that no id or name carries a role word, that the two
trees agree on the id set, that every instructor reference resolves, and that the
true path still grades as a hit.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.cloudforge.io.loaders import load_yaml
from app.cloudforge.lab.grade import grade_submission
from app.cloudforge.lab.pack import LabRequest, write_lab
from app.cloudforge.lab.paths import LabPaths
from app.cloudforge.lab.submission import LabSubmission, PathGuess
from app.cloudforge.models.scenario import ScenarioSpec

_EXAMPLES = sorted(Path("examples").glob("*.yaml"))
_SEEDS = (0, 17)
_CASES = [
    pytest.param(example, seed, id=f"{example.stem}-{seed}")
    for example in _EXAMPLES
    for seed in _SEEDS
]
_ROLE_WORDS = re.compile(
    r"core0_|decoy|noise|false_positive|fp0_|ctrl0_|honeypot|compensat", re.IGNORECASE
)
# The namespace shape shipped before 1.3.1: ``core0_c602/``, ``noise13_9510/``, ``decoy0/``.
_OLD_NAMESPACE = re.compile(r"\b(core|decoy|noise|fp|ctrl)\d+(_[0-9a-f]{4})?/")
# scenario.yaml is the input spec copied verbatim; its schema names ``false_positives``
# as a requirement count, which is not an id or a name, so it gets the shape check only.
_STUDENT_TEXT_FILES = ("brief.md",)

_CACHE: dict[tuple[str, int], LabPaths] = {}


def _lab(tmp_path_factory: pytest.TempPathFactory, example: Path, seed: int) -> LabPaths:
    key = (example.stem, seed)
    if key not in _CACHE:
        spec = ScenarioSpec.model_validate(load_yaml(example))
        out = LabPaths.from_dir(tmp_path_factory.mktemp(f"{example.stem}-{seed}-"))
        write_lab(LabRequest(spec=spec, seed=seed), out)
        _CACHE[key] = out
    return _CACHE[key]


def _json(path: Path) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _node_ids(graph_like: dict[str, object]) -> set[str]:
    nodes = graph_like["nodes"]
    assert isinstance(nodes, list)
    return {str(n["id"]) for n in nodes}


def _student_identifiers(estate: dict[str, object]) -> list[str]:
    nodes, edges = estate["nodes"], estate["edges"]
    assert isinstance(nodes, list) and isinstance(edges, list)
    ids = [str(n["id"]) for n in nodes] + [str(n["name"]) for n in nodes]
    return ids + [str(e["from"]) for e in edges] + [str(e["to"]) for e in edges]


def test_every_example_has_a_case() -> None:
    assert len(_EXAMPLES) >= 15, [p.name for p in _EXAMPLES]


@pytest.mark.parametrize(("example", "seed"), _CASES)
def test_student_ids_and_names_carry_no_role_words(
    tmp_path_factory: pytest.TempPathFactory, example: Path, seed: int
) -> None:
    lab = _lab(tmp_path_factory, example, seed)
    estate = _json(lab.estate_json)
    for text in _student_identifiers(estate):
        assert not _ROLE_WORDS.search(text), text
        assert not _OLD_NAMESPACE.search(text), text
    # estate.html embeds the same estate JSON verbatim; its own template text is not
    # generated per lab, so the identifiers above are exactly what the page shows.
    html = lab.estate_html.read_text(encoding="utf-8")
    assert json.dumps(estate) in html
    assert not _OLD_NAMESPACE.search(html)
    for name in _STUDENT_TEXT_FILES:
        text = (lab.student / name).read_text(encoding="utf-8")
        assert not _ROLE_WORDS.search(text), name
        assert not _OLD_NAMESPACE.search(text), name
    assert not _OLD_NAMESPACE.search((lab.student / "scenario.yaml").read_text(encoding="utf-8"))
    for tf in (lab.student / "terraform").glob("*.tf"):
        text = tf.read_text(encoding="utf-8")
        assert not _ROLE_WORDS.search(text), tf.name
        assert not _OLD_NAMESPACE.search(text), tf.name


@pytest.mark.parametrize(("example", "seed"), _CASES)
def test_student_and_instructor_trees_share_one_id_set(
    tmp_path_factory: pytest.TempPathFactory, example: Path, seed: int
) -> None:
    lab = _lab(tmp_path_factory, example, seed)
    student_ids = _node_ids(_json(lab.estate_json))
    instructor_ids = _node_ids(_json(lab.instructor / "graph.json"))
    assert student_ids == instructor_ids
    assert len(student_ids) == len(_json(lab.estate_json)["nodes"])  # type: ignore[arg-type]


@pytest.mark.parametrize(("example", "seed"), _CASES)
def test_instructor_references_resolve_to_graph_nodes(
    tmp_path_factory: pytest.TempPathFactory, example: Path, seed: int
) -> None:
    lab = _lab(tmp_path_factory, example, seed)
    graph_ids = _node_ids(_json(lab.instructor / "graph.json"))
    paths = _json(lab.instructor / "ground_truth_paths.json")["paths"]
    findings = _json(lab.instructor / "expected_findings.json")["findings"]
    assert isinstance(paths, list) and isinstance(findings, list) and paths
    for path in paths:
        assert set(path["nodes"]) <= graph_ids, path["id"]
    for finding in findings:
        assert set(finding["resource_ids"]) <= graph_ids, finding["id"]


@pytest.mark.parametrize(("example", "seed"), _CASES)
def test_grading_the_true_path_from_the_student_estate_hits(
    tmp_path_factory: pytest.TempPathFactory, example: Path, seed: int
) -> None:
    lab = _lab(tmp_path_factory, example, seed)
    key = _json(lab.grade_key)
    student_ids = _node_ids(_json(lab.estate_json))
    truth = key["paths"]
    assert isinstance(truth, list) and truth
    for path in truth:
        nodes = [str(n) for n in path["nodes"]]
        assert set(nodes) <= student_ids  # the student can name every hop
        result = grade_submission(key, LabSubmission(paths=[PathGuess(nodes=nodes)]))
        assert path["id"] in result.path_hits
        assert result.extras == []
