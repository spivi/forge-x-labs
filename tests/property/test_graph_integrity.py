"""Property tests: graph referential integrity (S4).

Stresses two layers that are supposed to compose into one guarantee:

1. The Pydantic model layer (``ScenarioGraph._edges_reference_existing_nodes``) —
   an edge with a missing endpoint must never construct a graph.
2. The ``GraphRiskEngine`` layer — a critical path with a missing hop, or a
   critical-risk edge disconnected from the ``stores_sensitive_data`` sink, must
   FAIL validation (S4: "No graph can claim a critical path unless that path is
   actually connected.").

Every assertion below is commented with the clause it proves.
"""

from __future__ import annotations

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from app.cloudforge.generate.base import ScenarioBundle
from app.cloudforge.models.findings import GroundTruthPath, GroundTruthPaths
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
from app.cloudforge.validate.graph_risk import GraphRiskEngine
from app.cloudforge.validate.results import Status
from tests.property.strategies import (
    GENEROUS_SPEC,
    bundle_for,
    edge_types,
    extra_node_ids,
    make_edge,
    real_bundles,
    valid_graphs,
    valid_node_lists,
)

_EXAMPLES = 500
_STRESS_EXAMPLES = 5000


def _outcome(engine: GraphRiskEngine, label: str) -> Status:
    return next(o.status for o in engine.run() if o.label == label)


# --- 1. valid graph -> ScenarioGraph validates ------------------------------------


@given(valid_graphs())
@settings(max_examples=_EXAMPLES, suppress_health_check=[HealthCheck.too_slow])
def test_valid_graph_always_constructs(graph: ScenarioGraph) -> None:
    """Every edge references an existing node by construction -> S4 holds trivially."""
    # S4: a graph whose edges only ever reference generated node ids must validate —
    # referential integrity is satisfiable, not accidentally always-rejecting.
    assert isinstance(graph, ScenarioGraph)
    node_id_set = {n.id for n in graph.nodes}
    for edge in graph.edges:
        assert edge.from_ in node_id_set  # S4
        assert edge.to in node_id_set  # S4


@given(real_bundles())
@settings(max_examples=_EXAMPLES, suppress_health_check=[HealthCheck.too_slow])
def test_real_generator_bundles_satisfy_critical_sink_connectivity(
    bundle: ScenarioBundle,
) -> None:
    """Both shipped generators (ci_cd_iam_chain, public_data_exposure) satisfy S4.

    Exercises the real ``build_graph``/``build_findings``/``build_ground_truth``
    functions (not synthetic Hypothesis-only shapes) through the real
    ``GraphRiskEngine`` — the critical-sink-connectivity check must PASS for every
    scenario family the product actually ships.
    """
    engine = GraphRiskEngine(bundle, GENEROUS_SPEC)
    status = _outcome(engine, "critical-sink connectivity")
    assert status is Status.PASS  # S4: shipped generators are connected by construction


# --- 2. edge with a missing endpoint -> rejected by the model validator ----------


@given(
    valid_node_lists(min_size=2, max_size=6),
    extra_node_ids,
    edge_types,
)
@settings(max_examples=_EXAMPLES, suppress_health_check=[HealthCheck.too_slow])
def test_edge_with_missing_endpoint_rejected(
    nodes: list, missing_id: str, edge_type: EdgeType
) -> None:
    """An edge pointing at a node id that does not exist must be rejected (S4)."""
    ids = {n.id for n in nodes}
    if missing_id in ids:
        # `extra_node_ids` uses an "x-" prefix disjoint from `node_ids`'s "n-" prefix,
        # so this branch should be unreachable; guard anyway for strategy-shrinking.
        return
    src = nodes[0].id
    bad_edge = make_edge(src, missing_id, edge_type, "high")
    try:
        graph = ScenarioGraph(nodes=nodes, edges=[bad_edge])
    except ValueError:
        return  # S4: rejected — the guarantee.
    raise AssertionError(
        f"graph with missing-endpoint edge {bad_edge.key} incorrectly validated: {graph}"
    )


@given(
    valid_node_lists(min_size=2, max_size=6),
    extra_node_ids,
    edge_types,
)
@settings(max_examples=_EXAMPLES, suppress_health_check=[HealthCheck.too_slow])
def test_edge_with_missing_source_rejected(
    nodes: list, missing_id: str, edge_type: EdgeType
) -> None:
    """Same as above but the MISSING endpoint is the source, not the destination (S4)."""
    ids = {n.id for n in nodes}
    if missing_id in ids:
        return
    dst = nodes[0].id
    bad_edge = make_edge(missing_id, dst, edge_type, "high")
    try:
        graph = ScenarioGraph(nodes=nodes, edges=[bad_edge])
    except ValueError:
        return  # S4: rejected.
    raise AssertionError(
        f"graph with missing-source edge {bad_edge.key} incorrectly validated: {graph}"
    )


# --- 3. duplicate node ids: model does not currently police this — document what IS
#        true: a graph with duplicate node ids but well-formed edges still validates
#        at the model layer, since `ScenarioGraph` only checks edges reference *some*
#        matching id, not id uniqueness. Recorded (not a clause) so a future clause
#        addition has a locked baseline. ----------------------------------------------


@given(valid_node_lists(min_size=1, max_size=1))
@settings(max_examples=_EXAMPLES, suppress_health_check=[HealthCheck.too_slow])
def test_duplicate_node_ids_not_rejected_by_model(nodes: list) -> None:
    """Baseline: duplicate node ids are NOT currently a model-validator concern.

    Not an S4 violation — S4 is about edge-endpoint referential integrity, and an
    edge referencing an id that exists (even if it exists twice) still resolves.
    Locks in current behavior so a future integrity clause has a documented starting
    point rather than silent scope creep.
    """
    dup = nodes[0]
    graph = ScenarioGraph(nodes=[dup, dup], edges=[])
    assert len(graph.nodes) == 2  # documented baseline, not a contract clause


# --- 4. isolated critical sink: a stores_sensitive_data edge with NO critical edge
#        anywhere in the graph -> PASS (S4 only requires connectivity WHEN a critical
#        edge exists elsewhere; vacuous truth is intentional per graph_risk.py). ------


@given(valid_node_lists(min_size=2, max_size=2))
@settings(max_examples=_EXAMPLES, suppress_health_check=[HealthCheck.too_slow])
def test_isolated_critical_sink_alone_passes(nodes: list) -> None:
    """A lone stores_sensitive_data edge with no critical edge elsewhere -> PASS.

    S4 requires a critical edge to REACH the sink; if there is no critical edge at
    all, the check is vacuously satisfied (graph_risk.py: `if not critical_edges or
    not sink_edges: return PASS`). This locks in that intentional design.
    """
    a, b = nodes[0].id, nodes[1].id
    sink_edge = make_edge(a, b, EdgeType.STORES_SENSITIVE_DATA, "critical")
    graph = ScenarioGraph(nodes=nodes, edges=[sink_edge])
    bundle = bundle_for(graph)

    status = _outcome(GraphRiskEngine(bundle, GENEROUS_SPEC), "critical-sink connectivity")
    assert status is Status.PASS  # S4: vacuous truth, no critical edge to fail on


# --- 5. critical edge DISCONNECTED from the sensitive sink -> graph_risk FAILs ----


@given(
    valid_node_lists(min_size=4, max_size=4),
    edge_types.filter(lambda t: t != EdgeType.STORES_SENSITIVE_DATA),
)
@settings(max_examples=_EXAMPLES, suppress_health_check=[HealthCheck.too_slow])
def test_disconnected_critical_edge_fails_connectivity(nodes: list, edge_type: EdgeType) -> None:
    """A critical edge on one component and a sink on a disconnected component FAILs (S4)."""
    a, b, c, d = (n.id for n in nodes)
    critical_edge = make_edge(a, b, edge_type, "critical")
    sink_edge = make_edge(c, d, EdgeType.STORES_SENSITIVE_DATA, "critical")
    graph = ScenarioGraph(nodes=nodes, edges=[critical_edge, sink_edge])
    bundle = bundle_for(graph)

    status = _outcome(GraphRiskEngine(bundle, GENEROUS_SPEC), "critical-sink connectivity")
    assert status is Status.FAIL  # S4: disconnected critical path must FAIL


# --- 6. critical path with a missing hop -> graph_risk rejects (path-exists check) -


@given(valid_node_lists(min_size=3, max_size=3), edge_types)
@settings(max_examples=_EXAMPLES, suppress_health_check=[HealthCheck.too_slow])
def test_ground_truth_path_missing_hop_fails(nodes: list, edge_type: EdgeType) -> None:
    """A ground-truth path claims a hop with no backing edge in the graph -> FAIL (S4)."""
    a, b, c = (n.id for n in nodes)
    # Graph only has an edge a->b; ground truth claims a 3-node path a->b->c.
    graph = ScenarioGraph(nodes=nodes, edges=[make_edge(a, b, edge_type, "high")])
    ground_truth = GroundTruthPaths(
        paths=[
            GroundTruthPath(
                id="path-missing-hop",
                severity="critical",
                nodes=[a, b, c],
                edges=[f"{a}->{edge_type.value}->{b}", f"{b}->{edge_type.value}->{c}"],
                explanation="synthetic missing-hop path",
            )
        ]
    )
    bundle = bundle_for(graph, ground_truth=ground_truth)

    status = _outcome(GraphRiskEngine(bundle, GENEROUS_SPEC), "ground-truth path exists")
    assert status is Status.FAIL  # S4: a claimed hop with no edge must FAIL


# --- 7. edge-type mismatch / unknown resource types: model-level enum enforcement -


@given(st.text(min_size=1, max_size=20))
@settings(max_examples=_EXAMPLES, suppress_health_check=[HealthCheck.too_slow])
def test_unknown_node_type_rejected_by_enum(raw_type: str) -> None:
    """An unknown resource `type` string is rejected by the NodeType enum (S4 precondition).

    S4 assumes nodes have a well-typed `type`; Pydantic's StrEnum coercion is the
    guard that makes that assumption safe. A value that happens to collide with a
    real enum member is expected to succeed — only genuinely-unknown strings must
    raise.
    """
    known_values = {t.value for t in NodeType}
    tags = NodeTags(env="t", owner="t", app="t")
    if raw_type in known_values:
        node = GraphNode(
            id="n-1",
            type=raw_type,  # type: ignore[arg-type]
            name="whatever",
            tags=tags,
            security=NodeSecurity(criticality="low"),
        )
        assert node.type.value == raw_type
        return
    try:
        GraphNode(
            id="n-1",
            type=raw_type,  # type: ignore[arg-type]
            name="whatever",
            tags=tags,
            security=NodeSecurity(criticality="low"),
        )
    except ValidationError:
        return  # S4 precondition: unknown resource type rejected.
    raise AssertionError(f"unknown node type {raw_type!r} incorrectly accepted")


@given(st.text(min_size=1, max_size=20))
@settings(max_examples=_EXAMPLES, suppress_health_check=[HealthCheck.too_slow])
def test_unknown_edge_type_rejected_by_enum(raw_type: str) -> None:
    """An unknown edge `type` string is rejected by the EdgeType enum (S4 precondition)."""
    known_values = {t.value for t in EdgeType}
    if raw_type in known_values:
        edge = GraphEdge(
            from_="n-1",
            to="n-2",
            type=raw_type,
            security=EdgeSecurity(risk="low"),  # type: ignore[arg-type]
        )
        assert edge.type.value == raw_type
        return
    try:
        GraphEdge(
            from_="n-1",
            to="n-2",
            type=raw_type,
            security=EdgeSecurity(risk="low"),  # type: ignore[arg-type]
        )
    except ValidationError:
        return  # S4 precondition: unknown edge type rejected.
    raise AssertionError(f"unknown edge type {raw_type!r} incorrectly accepted")


# --- stress variant: same invariant, 10x the examples --------------------------------


@pytest.mark.stress
@given(
    valid_node_lists(min_size=2, max_size=6),
    extra_node_ids,
    edge_types,
)
@settings(max_examples=_STRESS_EXAMPLES, suppress_health_check=[HealthCheck.too_slow])
def test_edge_with_missing_endpoint_rejected_stress(
    nodes: list, missing_id: str, edge_type: EdgeType
) -> None:
    """5,000-example stress variant of the missing-endpoint rejection property (S4)."""
    ids = {n.id for n in nodes}
    if missing_id in ids:
        return
    src = nodes[0].id
    bad_edge = make_edge(src, missing_id, edge_type, "high")
    try:
        ScenarioGraph(nodes=nodes, edges=[bad_edge])
    except ValueError:
        return  # S4: rejected.
    raise AssertionError(f"graph with missing-endpoint edge {bad_edge.key} incorrectly validated")
