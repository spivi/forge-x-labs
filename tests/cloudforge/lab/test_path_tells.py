"""Nothing a path node carries may be rare among its type peers.

The class of giveaway this keeps out: every core fragment stamps one fixed tag
set (``env=prod``, ``owner=azure-platform``) while padding drew from other
lists, so filtering on a tag returned the path; the sink was the only CamelCase
data set; the path identity was the only ``SystemAssigned`` one. For every
example at seeds 0 and 17 and all three difficulties this reads the student
estate plus the instructor's paths and checks, for every path node:

- every tag value and every attribute value appears on at least two off-path
  nodes of the same type when that type has three or more instances, on at
  least one otherwise (capped by how many same-type off-path nodes exist; for
  tags, any off-path node when the type has no peers at all);
- the name's casing style (CamelCase / kebab / snake) is shared by an
  off-path node of the same type (any off-path node when there are no peers).

Attributes that legitimately exist only on a path node are the allowlist below:
the modeled risk itself and per-resource identifiers. It is spelled out here so
a reviewer sees it, printed by ``test_allowlist_is_the_reviewed_one``, and held
to ``composer_blend``, which must never copy those attributes onto padding.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from app.cloudforge.generate import composer_blend
from app.cloudforge.generate.composer import GraphComposer
from app.cloudforge.io.loaders import load_yaml
from app.cloudforge.lab.strip import strip_graph
from app.cloudforge.models.scenario import ScenarioSpec

# The modeled misconfiguration: the student is meant to be able to find these.
RISK_ATTRIBUTES = frozenset(
    {
        "acl",
        "actions",
        "auth_type",
        "encrypted",
        "imds_version",
        "logging",
        "principal",
        "public",
        "public_access",
        "publicly_accessible",
        "trusted_principal",
    }
)
# Unique per resource by nature; a copy would name a different resource.
IDENTIFIER_ATTRIBUTES = frozenset(
    {
        "account_id",
        "annotations",
        "bucket_name",
        "email",
        "principal_id",
        "role_arn",
        "service_account",
        "storage_account",
    }
)
ALLOWLIST = RISK_ATTRIBUTES | IDENTIFIER_ATTRIBUTES

_EXAMPLES = sorted(Path("examples").glob("*.yaml"))
_SEEDS = (0, 17)
_DIFFICULTIES = ("easy", "medium", "hard")
_CASES = [
    pytest.param(example, difficulty, seed, id=f"{example.stem}-{difficulty}-{seed}")
    for example in _EXAMPLES
    for difficulty in _DIFFICULTIES
    for seed in _SEEDS
]
_TAG_KEYS = ("env", "owner", "app")
_CROWD = 3
_PEERS_WANTED = 2
_CACHE: dict[tuple[str, str, int], tuple[dict[str, Any], set[str]]] = {}


def _estate(example: Path, difficulty: str, seed: int) -> tuple[dict[str, Any], set[str]]:
    key = (example.stem, difficulty, seed)
    if key not in _CACHE:
        data = load_yaml(example)
        data["difficulty"] = difficulty
        spec = ScenarioSpec.model_validate(data)
        bundle = GraphComposer(spec, seed=seed).generate()
        on_path = {nid for path in bundle.ground_truth.paths for nid in path.nodes}
        _CACHE[key] = (strip_graph(bundle.graph), on_path)
    return _CACHE[key]


def _style(name: str) -> str:
    if re.search(r"[A-Z]", name):
        return "camel"
    if "_" in name:
        return "snake"
    return "kebab"


def _tells(estate: dict[str, Any], on_path: set[str]) -> list[str]:
    nodes = estate["nodes"]
    counts = Counter(n["type"] for n in nodes)
    off_path = [n for n in nodes if n["id"] not in on_path]
    found: list[str] = []
    for node in (n for n in nodes if n["id"] in on_path):
        ntype = node["type"]
        peers = [n for n in off_path if n["type"] == ntype]
        wanted = _PEERS_WANTED if counts[ntype] >= _CROWD else 1
        for key in _TAG_KEYS:
            value = node["tags"][key]
            pool = peers or off_path
            need = min(wanted, len(pool)) if peers else 1
            have = sum(1 for n in pool if n["tags"][key] == value)
            if have < need:
                found.append(f"{ntype} {node['name']}: tag {key}={value!r} on {have}, need {need}")
        for key, value in node["attributes"].items():
            if key in ALLOWLIST:
                continue
            if not peers:
                found.append(f"{ntype} {node['name']}: attribute {key} on a type with no peers")
                continue
            need = min(wanted, len(peers))
            have = sum(1 for n in peers if n["attributes"].get(key) == value)
            if have < need:
                shown = json.dumps(value)
                found.append(f"{ntype} {node['name']}: attr {key}={shown} on {have}, need {need}")
        style = _style(node["name"])
        if not any(_style(n["name"]) == style for n in (peers or off_path)):
            found.append(f"{ntype} {node['name']}: name style {style} shared by no off-path node")
    return found


def test_allowlist_is_the_reviewed_one() -> None:
    print("\nrisk attributes (the modeled misconfiguration):", sorted(RISK_ATTRIBUTES))
    print("identifier attributes (unique per resource):", sorted(IDENTIFIER_ATTRIBUTES))
    assert RISK_ATTRIBUTES == composer_blend.RISK_ATTRIBUTES
    assert IDENTIFIER_ATTRIBUTES == composer_blend.IDENTIFIER_ATTRIBUTES
    assert ALLOWLIST == composer_blend.EXEMPT_ATTRIBUTES
    assert len(ALLOWLIST) <= 20, "keep the allowlist short enough to review"


@pytest.mark.parametrize(("example", "difficulty", "seed"), _CASES)
def test_path_nodes_carry_nothing_rare_among_their_peers(
    example: Path, difficulty: str, seed: int
) -> None:
    estate, on_path = _estate(example, difficulty, seed)
    assert on_path, "every example has a ground-truth path"
    found = _tells(estate, on_path)
    assert not found, "\n".join(found)


@pytest.mark.parametrize("example", _EXAMPLES, ids=[e.stem for e in _EXAMPLES])
def test_data_set_names_are_kebab_case_everywhere(example: Path) -> None:
    estate, _on_path = _estate(example, "medium", 0)
    for node in estate["nodes"]:
        if node["type"] == "DataSet":
            assert _style(node["name"]) == "kebab", node["name"]
