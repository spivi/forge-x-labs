"""End-to-end CLI tests via Typer's CliRunner."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from app.cli import app
from app.cloudforge.generate.base import ScenarioBundle
from app.cloudforge.generate.template_generator import TemplateGenerator
from app.cloudforge.models.findings import ExpectedFindings, GroundTruthPaths
from app.cloudforge.models.graph import (
    GraphNode,
    NodeSecurity,
    NodeTags,
    NodeType,
    ScenarioGraph,
)
from app.cloudforge.validate import tool_probe

runner = CliRunner()


@pytest.fixture(autouse=True)
def _no_external_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tool_probe, "detect_tool", lambda name: False)


def test_generate_then_validate_then_report_succeeds(tmp_path: Path) -> None:
    out = tmp_path / "scenario_001"

    gen = runner.invoke(app, ["generate", "examples/ci_cd_iam_chain.yaml", "--out", str(out)])
    val = runner.invoke(app, ["validate", str(out)])
    rep = runner.invoke(app, ["report", str(out)])

    assert gen.exit_code == 0
    assert val.exit_code == 0
    assert rep.exit_code == 0


def test_generate_missing_input_exits_error(tmp_path: Path) -> None:
    result = runner.invoke(app, ["generate", "does-not-exist.yaml", "--out", str(tmp_path / "s")])

    assert result.exit_code == 1


def test_generated_tree_has_expected_files(tmp_path: Path) -> None:
    out = tmp_path / "scenario_001"

    runner.invoke(app, ["generate", "examples/ci_cd_iam_chain.yaml", "--out", str(out)])

    assert (out / "graph.json").exists()
    assert (out / "terraform" / "iam.tf").exists()


def test_generate_on_colliding_graph_exits_with_clean_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A label collision must surface as a clean CLI error, not a raw traceback.

    The emitter runs inside ``write_all``; patch the generator to hand ``generate`` a
    bundle whose graph has two distinct ids (``a-b``/``a_b``) that sanitize to the same
    ``aws_s3_bucket`` label, and assert the CLI exits 1 with a clean, id-naming error.
    """
    colliding = _colliding_bundle()
    monkeypatch.setattr(TemplateGenerator, "generate", lambda self, spec: colliding)

    result = runner.invoke(
        app,
        [
            "generate",
            "examples/ci_cd_iam_chain.yaml",
            "--out",
            str(tmp_path / "s"),
            "--engine",
            "template",
        ],
    )

    assert result.exit_code == 1
    # Clean error naming both colliding ids — NOT a raw terraform / traceback failure.
    assert "error:" in result.stdout
    assert "a-b" in result.stdout
    assert "a_b" in result.stdout
    assert "Traceback" not in result.stdout


def _colliding_bundle() -> ScenarioBundle:
    graph = ScenarioGraph(nodes=[_bucket_node("a-b"), _bucket_node("a_b")], edges=[])
    return ScenarioBundle(
        graph=graph,
        findings=ExpectedFindings(findings=[]),
        ground_truth=GroundTruthPaths(paths=[]),
    )


def _bucket_node(node_id: str) -> GraphNode:
    return GraphNode(
        id=node_id,
        type=NodeType.S3_BUCKET,
        name="collide",
        tags=NodeTags(env="staging", owner="platform-team", app="analytics-exporter"),
        security=NodeSecurity(criticality="low"),
        attributes={},
    )


def test_version_command_prints_version() -> None:
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert result.stdout.strip()
