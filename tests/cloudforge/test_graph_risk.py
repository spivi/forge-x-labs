"""Graph-risk engine tests (check 3: critical path exists, check 6: forbidden perms)."""

from __future__ import annotations

import pytest

from app.cloudforge.generate.template_generator import TemplateGenerator
from app.cloudforge.models.graph import (
    EdgeType,
    GraphNode,
    NodeSecurity,
    NodeTags,
    NodeType,
)
from app.cloudforge.models.scenario import ScenarioSpec
from app.cloudforge.validate.graph_risk import GraphRiskEngine
from app.cloudforge.validate.results import Status

_TAGS = NodeTags(env="staging", owner="platform-team", app="analytics-exporter")


def _outcome(engine: GraphRiskEngine, label: str) -> Status:
    return next(o.status for o in engine.run() if o.label == label)


def test_critical_path_exists_returns_pass(example_spec: ScenarioSpec) -> None:
    bundle = TemplateGenerator().generate(example_spec)

    status = _outcome(GraphRiskEngine(bundle, example_spec), "ground-truth path exists")

    assert status is Status.PASS


def test_missing_edge_returns_fail(example_spec: ScenarioSpec) -> None:
    bundle = TemplateGenerator().generate(example_spec)
    bundle.graph.edges = [e for e in bundle.graph.edges if e.type is not EdgeType.CAN_PASS_ROLE]

    status = _outcome(GraphRiskEngine(bundle, example_spec), "ground-truth path exists")

    assert status is Status.FAIL


@pytest.mark.parametrize(
    "action",
    ["iam:DeleteRole", "s3:DeleteBucket", "ec2:TerminateInstances", "organizations:CreateAccount"],
)
def test_forbidden_permission_present_returns_fail(
    example_spec: ScenarioSpec, action: str
) -> None:
    bundle = TemplateGenerator().generate(example_spec)
    bundle.graph.nodes.append(_policy_node_with_action(action))

    status = _outcome(GraphRiskEngine(bundle, example_spec), "no forbidden permissions")

    assert status is Status.FAIL


def test_no_forbidden_permission_returns_pass(example_spec: ScenarioSpec) -> None:
    bundle = TemplateGenerator().generate(example_spec)

    status = _outcome(GraphRiskEngine(bundle, example_spec), "no forbidden permissions")

    assert status is Status.PASS


def _policy_node_with_action(action: str) -> GraphNode:
    return GraphNode(
        id="pol-danger",
        type=NodeType.IAM_POLICY,
        name="DangerPolicy",
        tags=_TAGS,
        security=NodeSecurity(criticality="high"),
        attributes={"actions": [action]},
    )
