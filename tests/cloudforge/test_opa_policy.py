"""Real ``opa eval`` tests for the family-agnostic critical-chain policy (FXL-54).

The OPA policy (``policies/scenario.rego``) is a coarse, *family-agnostic* sanity
gate: it must PASS every family the tool generates while still DENYing a genuinely
broken scenario. These tests run the *real* ``opa`` binary over each family's
generated ``graph.json`` — so they gate on ``opa`` being installed and skip
fail-soft when it is absent, mirroring how the terraform emitter tests gate on
``terraform``. (CI has no ``opa`` and therefore skips cleanly.)

Broken-graph cases mutate a real generated graph so the fixtures stay in lockstep
with the schema instead of hand-rolling nodes/edges.
"""

from __future__ import annotations

import copy
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from app.cloudforge.generate import ci_cd_iam_chain, public_data_exposure
from app.cloudforge.models.graph import ScenarioGraph

_POLICY = Path("policies/scenario.rego")

_opa_required = pytest.mark.skipif(
    shutil.which("opa") is None,
    reason="opa binary not installed — skipping real opa eval (fail-soft, like terraform tests)",
)


def _graph_dict(build_graph: Any) -> dict[str, Any]:
    """Serialize a family's real graph to the on-disk ``graph.json`` shape."""
    graph: ScenarioGraph = build_graph()
    return json.loads(graph.model_dump_json(by_alias=True))


def _opa_denials(graph: dict[str, Any], tmp_path: Path) -> list[str]:
    """Run the real ``opa eval`` over ``graph`` and return the deny messages."""
    graph_path = tmp_path / "graph.json"
    graph_path.write_text(json.dumps(graph), encoding="utf-8")
    result = subprocess.run(  # noqa: S603 — fixed argv, no shell, opa from PATH
        [  # noqa: S607
            "opa",
            "eval",
            "-i",
            str(graph_path),
            "-d",
            str(_POLICY),
            "data.cloudforge.deny",
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(result.stdout or "{}")
    expressions = payload.get("result", [])
    return [
        v for r in expressions for e in r.get("expressions", []) for v in (e.get("value") or [])
    ]


# --- both real families PASS (family-agnostic) -------------------------------


@_opa_required
def test_public_data_exposure_graph_has_no_denials(tmp_path: Path) -> None:
    graph = _graph_dict(public_data_exposure.build_graph)

    assert _opa_denials(graph, tmp_path) == []


@_opa_required
def test_ci_cd_iam_chain_graph_has_no_denials(tmp_path: Path) -> None:
    graph = _graph_dict(ci_cd_iam_chain.build_graph)

    assert _opa_denials(graph, tmp_path) == []


# --- the critical-chain gate still DENIES genuinely broken scenarios ----------


@_opa_required
def test_no_critical_risk_edge_denies(tmp_path: Path) -> None:
    """Downgrade every critical edge -> no critical-risk edge remains -> deny."""
    graph = _graph_dict(public_data_exposure.build_graph)
    for edge in graph["edges"]:
        if edge["security"]["risk"] == "critical":
            edge["security"]["risk"] = "low"

    denials = _opa_denials(graph, tmp_path)

    assert any("critical" in msg for msg in denials), denials


@_opa_required
def test_no_sensitive_data_sink_denies(tmp_path: Path) -> None:
    """Strip the ``stores_sensitive_data`` sink edges -> deny."""
    graph = _graph_dict(public_data_exposure.build_graph)
    graph["edges"] = [e for e in graph["edges"] if e["type"] != "stores_sensitive_data"]

    denials = _opa_denials(graph, tmp_path)

    assert any("sensitive" in msg for msg in denials), denials


# --- non-chain deny rules are unchanged and still fire ------------------------


@_opa_required
def test_missing_required_tag_still_denies(tmp_path: Path) -> None:
    graph = _graph_dict(public_data_exposure.build_graph)
    graph["nodes"][0]["tags"].pop("owner", None)

    denials = _opa_denials(graph, tmp_path)

    assert any("missing required tag" in msg for msg in denials), denials


@_opa_required
def test_forbidden_destructive_perm_still_denies(tmp_path: Path) -> None:
    graph = _graph_dict(ci_cd_iam_chain.build_graph)
    policy_node = next(n for n in graph["nodes"] if n["type"] == "IAMPolicy")
    policy_node["attributes"]["actions"] = ["s3:DeleteBucket"]

    denials = _opa_denials(graph, tmp_path)

    assert any("forbidden permission" in msg for msg in denials), denials


@_opa_required
def test_over_resource_budget_still_denies(tmp_path: Path) -> None:
    graph = _graph_dict(public_data_exposure.build_graph)
    template = copy.deepcopy(graph["nodes"][0])
    # Inflate past the coarse OPA budget ceiling (500 — the largest deployable
    # scale tier) with unique, well-tagged nodes.
    graph["nodes"] = [{**copy.deepcopy(template), "id": f"filler-{i}"} for i in range(505)]

    denials = _opa_denials(graph, tmp_path)

    assert any("exceeds max" in msg for msg in denials), denials
