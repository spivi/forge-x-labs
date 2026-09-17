"""Graph-risk engine tests (check 3: critical path exists, check 6: forbidden perms)."""

from __future__ import annotations

import pytest

from app.cloudforge.generate.base import ScenarioBundle
from app.cloudforge.generate.template_generator import TemplateGenerator
from app.cloudforge.models.findings import (
    ExpectedFindings,
    GroundTruthPath,
    GroundTruthPaths,
    SinkKind,
)
from app.cloudforge.models.graph import (
    EdgeSecurity,
    EdgeType,
    GraphEdge,
    GraphNode,
    NodeSecurity,
    NodeTags,
    NodeType,
    ScenarioGraph,
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


def test_critical_sink_connectivity_pass(example_spec: ScenarioSpec) -> None:
    """Verify that a normally-connected critical edge and sink pass the check."""
    bundle = TemplateGenerator().generate(example_spec)

    status = _outcome(GraphRiskEngine(bundle, example_spec), "critical-sink connectivity")

    assert status is Status.PASS


def _split_graph() -> ScenarioGraph:
    """A critical edge on one component and a data sink on another (FXL-79)."""
    return ScenarioGraph(
        nodes=[
            GraphNode(
                id="node-a",
                type=NodeType.IAM_ROLE,
                name="RoleA",
                tags=_TAGS,
                security=NodeSecurity(criticality="high"),
            ),
            GraphNode(
                id="node-b",
                type=NodeType.IAM_ROLE,
                name="RoleB",
                tags=_TAGS,
                security=NodeSecurity(criticality="high"),
            ),
            GraphNode(
                id="node-c",
                type=NodeType.S3_BUCKET,
                name="BucketC",
                tags=_TAGS,
                security=NodeSecurity(criticality="high"),
            ),
            GraphNode(
                id="node-d",
                type=NodeType.DATASET,
                name="DataD",
                tags=_TAGS,
                security=NodeSecurity(criticality="high"),
            ),
        ],
        edges=[
            GraphEdge(
                from_="node-a",
                to="node-b",
                type=EdgeType.CAN_PASS_ROLE,
                security=EdgeSecurity(risk="critical"),
            ),
            GraphEdge(
                from_="node-c",
                to="node-d",
                type=EdgeType.STORES_SENSITIVE_DATA,
                security=EdgeSecurity(risk="critical"),
            ),
        ],
    )


def _split_bundle(path: GroundTruthPath) -> ScenarioBundle:
    return ScenarioBundle(
        graph=_split_graph(),
        findings=ExpectedFindings(findings=[]),
        ground_truth=GroundTruthPaths(paths=[path]),
    )


def test_critical_sink_connectivity_unreachable_declared_target_fails(
    example_spec: ScenarioSpec,
) -> None:
    """A path that declares the data set on the other component as its target
    is rejected: no critical edge reaches what the path says is reached (FXL-79)."""
    path = GroundTruthPath(
        id="path-critical-01",
        severity="critical",
        nodes=["node-a", "node-b"],
        edges=["node-a->can_pass_role->node-b"],
        target="node-d",
        explanation="Critical path whose declared sink sits on a disconnected component",
    )

    engine = GraphRiskEngine(_split_bundle(path), example_spec)
    status = _outcome(engine, "critical-sink connectivity")

    assert status is Status.FAIL


def test_critical_sink_connectivity_accepts_a_reached_role_target(
    example_spec: ScenarioSpec,
) -> None:
    """The same split graph passes when the path says the role is what is reached:
    the rule follows the declared target, not only ``stores_sensitive_data`` edges."""
    path = GroundTruthPath(
        id="path-critical-01",
        severity="critical",
        nodes=["node-a", "node-b"],
        edges=["node-a->can_pass_role->node-b"],
        sink_kind=SinkKind.ROLE,
        target="node-b",
        explanation="Critical path ending at the role the attacker reaches",
    )

    engine = GraphRiskEngine(_split_bundle(path), example_spec)
    status = _outcome(engine, "critical-sink connectivity")

    assert status is Status.PASS


def test_critical_sink_connectivity_without_paths_still_needs_a_reachable_data_sink(
    example_spec: ScenarioSpec,
) -> None:
    """No declared paths: the original sink-edge rule still applies and the split
    graph is rejected (FXL-79)."""
    bundle = ScenarioBundle(
        graph=_split_graph(),
        findings=ExpectedFindings(findings=[]),
        ground_truth=GroundTruthPaths(paths=[]),
    )

    status = _outcome(GraphRiskEngine(bundle, example_spec), "critical-sink connectivity")

    assert status is Status.FAIL
