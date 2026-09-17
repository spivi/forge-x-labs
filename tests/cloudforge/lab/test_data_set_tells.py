"""The sink must not be the only labeled data set, nor the only one at its level.

Measured on 1.4.0 before this: an Azure or GCP estate held exactly one DataSet,
the sink, classified ``restricted``; an AWS estate's noise data sets were all
``internal`` while the sink carried no classification at all. Either way the
odd DataSet card was the answer. For every example at two seeds these tests
read the student estate plus the instructor's paths and check the board no
longer gives that away: several data sets, every one classified, off-path data
at ``confidential`` / ``restricted`` too, the sink sharing its level with at
least one other, and the sink's tags shared with other nodes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.cloudforge.generate.composer import GraphComposer
from app.cloudforge.generate.fragments._vocab import CLASSIFICATIONS
from app.cloudforge.io.loaders import load_yaml
from app.cloudforge.lab.strip import strip_graph
from app.cloudforge.models.scenario import ScenarioSpec

_EXAMPLES = sorted(Path("examples").glob("*.yaml"))
_SEEDS = (0, 17)
_CASES = [
    pytest.param(example, seed, id=f"{example.stem}-{seed}")
    for example in _EXAMPLES
    for seed in _SEEDS
]
_MIN_DATA_SETS = 3
_PROTECTED = {"confidential", "restricted"}
_CACHE: dict[tuple[str, int], tuple[dict[str, Any], set[str]]] = {}


def _estate(example: Path, seed: int) -> tuple[dict[str, Any], set[str]]:
    """The student estate and the set of node ids on any ground-truth path."""
    key = (example.stem, seed)
    if key not in _CACHE:
        spec = ScenarioSpec.model_validate(load_yaml(example))
        bundle = GraphComposer(spec, seed=seed).generate()
        on_path = {nid for path in bundle.ground_truth.paths for nid in path.nodes}
        _CACHE[key] = (strip_graph(bundle.graph), on_path)
    return _CACHE[key]


def _data_sets(estate: dict[str, Any]) -> list[dict[str, Any]]:
    return [n for n in estate["nodes"] if n["type"] == "DataSet"]


def _sinks(estate: dict[str, Any], on_path: set[str]) -> list[dict[str, Any]]:
    sinks = [n for n in _data_sets(estate) if n["id"] in on_path]
    assert sinks, "every example has a data-set sink on its path"
    return sinks


@pytest.mark.parametrize(("example", "seed"), _CASES)
def test_estate_holds_several_data_sets(example: Path, seed: int) -> None:
    estate, _on_path = _estate(example, seed)
    assert len(_data_sets(estate)) >= _MIN_DATA_SETS


@pytest.mark.parametrize(("example", "seed"), _CASES)
def test_every_data_set_carries_a_classification_from_the_spread(example: Path, seed: int) -> None:
    estate, _on_path = _estate(example, seed)
    for node in _data_sets(estate):
        assert node["attributes"].get("classification") in CLASSIFICATIONS, node["id"]


@pytest.mark.parametrize(("example", "seed"), _CASES)
def test_off_path_data_includes_a_confidential_or_restricted_set(example: Path, seed: int) -> None:
    estate, on_path = _estate(example, seed)
    off_path = {
        n["attributes"]["classification"] for n in _data_sets(estate) if n["id"] not in on_path
    }
    assert off_path & _PROTECTED, off_path


@pytest.mark.parametrize(("example", "seed"), _CASES)
def test_sink_is_not_the_only_data_set_at_its_classification(example: Path, seed: int) -> None:
    estate, on_path = _estate(example, seed)
    for sink in _sinks(estate, on_path):
        level = sink["attributes"]["classification"]
        peers = [
            n
            for n in _data_sets(estate)
            if n["id"] != sink["id"] and n["attributes"]["classification"] == level
        ]
        assert peers, (sink["id"], level)


@pytest.mark.parametrize(("example", "seed"), _CASES)
def test_sink_tags_are_shared_with_other_nodes(example: Path, seed: int) -> None:
    estate, on_path = _estate(example, seed)
    for sink in _sinks(estate, on_path):
        others = [n for n in estate["nodes"] if n["id"] != sink["id"]]
        for key in ("env", "owner", "app"):
            value = sink["tags"][key]
            assert any(n["tags"][key] == value for n in others), (sink["id"], key, value)
