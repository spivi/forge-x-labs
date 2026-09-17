"""KMS key + EBS snapshot emission."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.cloudforge.errors import GraphIntegrityError
from app.cloudforge.models.graph import GraphNode, NodeSecurity, NodeTags, NodeType, ScenarioGraph
from app.cloudforge.pipeline.terraform_emitter import TerraformEmitter


def _node(node_id: str, node_type: NodeType, **attrs: str | list[str]) -> GraphNode:
    return GraphNode(
        id=node_id,
        type=node_type,
        name=node_id,
        tags=NodeTags(env="prod", owner="sec", app="lab"),
        security=NodeSecurity(criticality="high"),
        attributes=dict(attrs),
    )


def test_kms_key_emits_policy_with_star_principal(tmp_path: Path) -> None:
    graph = ScenarioGraph(nodes=[_node("kms-data", NodeType.KMS_KEY, principal="*")], edges=[])
    kms = TerraformEmitter(graph).emit(tmp_path)
    text = next(p.read_text() for p in kms if p.name == "kms.tf")
    assert 'resource "aws_kms_key"' in text
    assert '"AWS": "*"' in text
    assert "kms:Decrypt" in text
    assert "${" not in text


def test_public_snapshot_emits_group_all_permission(tmp_path: Path) -> None:
    graph = ScenarioGraph(
        nodes=[_node("snap-public", NodeType.EBS_SNAPSHOT, public="true")],
        edges=[],
    )
    files = {p.name: p.read_text() for p in TerraformEmitter(graph).emit(tmp_path)}
    snap = files["snapshot.tf"]
    assert 'resource "aws_ebs_snapshot"' in snap
    assert "encrypted = false" in snap
    assert 'group       = "all"' in snap
    assert "vol-00000000" in snap


def test_kms_label_collision_raises(tmp_path: Path) -> None:
    graph = ScenarioGraph(
        nodes=[_node("a-b", NodeType.KMS_KEY), _node("a_b", NodeType.KMS_KEY)],
        edges=[],
    )
    with pytest.raises(GraphIntegrityError, match="a-b"):
        TerraformEmitter(graph).emit(tmp_path)
