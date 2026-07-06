"""Property tests: ground-truth path integrity (S4).

"Only a fully-connected path to the declared ``stores_sensitive_data`` sink passes."
Stresses ``GraphRiskEngine._check_ground_truth_nodes`` / ``_check_ground_truth_edges``
/ ``_check_paths_reachable`` against: nodes/edges that exist vs. are missing,
out-of-order edges, cycles, a wrong sink, and a wrong start identity.

Every assertion is commented with the clause it proves (S4).
"""

from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.cloudforge.models.findings import GroundTruthPath, GroundTruthPaths
from app.cloudforge.models.graph import EdgeType, ScenarioGraph
from app.cloudforge.validate.graph_risk import GraphRiskEngine
from app.cloudforge.validate.results import Status
from tests.property.strategies import (
    GENEROUS_SPEC,
    bundle_for,
    edge_types,
    extra_node_ids,
    make_edge,
    valid_node_lists,
)

_EXAMPLES = 500


def _outcomes(bundle_nodes: list, edges: list, path: GroundTruthPath) -> dict[str, Status]:
    graph = ScenarioGraph(nodes=bundle_nodes, edges=edges)
    bundle = bundle_for(graph, ground_truth=GroundTruthPaths(paths=[path]))
    engine = GraphRiskEngine(bundle, GENEROUS_SPEC)
    return {o.label: o.status for o in engine.run()}


# --- a fully-connected path to the real sink -> PASS all three ground-truth checks -


@given(valid_node_lists(min_size=3, max_size=3), edge_types)
@settings(max_examples=_EXAMPLES, suppress_health_check=[HealthCheck.too_slow])
def test_fully_connected_chain_passes(nodes: list, edge_type: EdgeType) -> None:
    """A path whose every hop has a real, in-order backing edge -> PASS (S4)."""
    a, b, c = (n.id for n in nodes)
    edges = [make_edge(a, b, edge_type, "high"), make_edge(b, c, edge_type, "high")]
    path = GroundTruthPath(
        id="path-ok",
        severity="high",
        nodes=[a, b, c],
        edges=[f"{a}->{edge_type.value}->{b}", f"{b}->{edge_type.value}->{c}"],
        explanation="fully connected",
    )
    outcomes = _outcomes(nodes, edges, path)
    assert outcomes["ground-truth nodes exist"] is Status.PASS  # S4
    assert outcomes["ground-truth edges exist"] is Status.PASS  # S4
    assert outcomes["ground-truth path exists"] is Status.PASS  # S4


# --- path references a node id that does not exist in the graph -> FAIL -----------


@given(valid_node_lists(min_size=2, max_size=2), extra_node_ids, edge_types)
@settings(max_examples=_EXAMPLES, suppress_health_check=[HealthCheck.too_slow])
def test_path_with_missing_node_fails(nodes: list, missing_id: str, edge_type: EdgeType) -> None:
    """A ground-truth path naming a node id absent from the graph -> FAIL (S4)."""
    a, b = (n.id for n in nodes)
    ids = {n.id for n in nodes}
    if missing_id in ids:
        return
    edges = [make_edge(a, b, edge_type, "high")]
    path = GroundTruthPath(
        id="path-missing-node",
        severity="high",
        nodes=[a, b, missing_id],
        edges=[f"{a}->{edge_type.value}->{b}"],
        explanation="references a node that does not exist",
    )
    outcomes = _outcomes(nodes, edges, path)
    assert outcomes["ground-truth nodes exist"] is Status.FAIL  # S4


# --- path references an edge key that does not exist in the graph -> FAIL ---------


@given(valid_node_lists(min_size=2, max_size=2), edge_types, edge_types)
@settings(max_examples=_EXAMPLES, suppress_health_check=[HealthCheck.too_slow])
def test_path_with_missing_edge_key_fails(
    nodes: list, real_type: EdgeType, claimed_type: EdgeType
) -> None:
    """A ground-truth path naming an edge key with no matching graph edge -> FAIL (S4)."""
    a, b = (n.id for n in nodes)
    if real_type == claimed_type:
        return  # need the claimed edge key to genuinely not exist
    edges = [make_edge(a, b, real_type, "high")]
    path = GroundTruthPath(
        id="path-missing-edge",
        severity="high",
        nodes=[a, b],
        edges=[f"{a}->{claimed_type.value}->{b}"],
        explanation="claims an edge type that was never built",
    )
    outcomes = _outcomes(nodes, edges, path)
    assert outcomes["ground-truth edges exist"] is Status.FAIL  # S4


# --- out-of-order edges: path.nodes sequence has no backing edge in that order ----


@given(valid_node_lists(min_size=3, max_size=3), edge_types)
@settings(max_examples=_EXAMPLES, suppress_health_check=[HealthCheck.too_slow])
def test_out_of_order_nodes_fails_reachability(nodes: list, edge_type: EdgeType) -> None:
    """Graph has only a->b and b->c; order [c, a, b] has no c->a edge -> FAIL (S4)."""
    a, b, c = (n.id for n in nodes)
    edges = [make_edge(a, b, edge_type, "high"), make_edge(b, c, edge_type, "high")]
    # Out-of-order traversal: c -> a is not a real edge.
    path = GroundTruthPath(
        id="path-out-of-order",
        severity="high",
        nodes=[c, a, b],
        edges=[f"{a}->{edge_type.value}->{b}", f"{b}->{edge_type.value}->{c}"],
        explanation="node order does not match any real walk",
    )
    outcomes = _outcomes(nodes, edges, path)
    assert outcomes["ground-truth path exists"] is Status.FAIL  # S4


# --- cycles: a path that loops back on itself must still resolve to real edges;
#     if it does, `_check_paths_reachable` PASSes (a cycle is still a walk) — this
#     documents that a cycle is not automatically invalid, only a genuinely missing
#     hop is. ---------------------------------------------------------------------


@given(valid_node_lists(min_size=2, max_size=2), edge_types)
@settings(max_examples=_EXAMPLES, suppress_health_check=[HealthCheck.too_slow])
def test_cycle_with_real_backing_edges_passes_reachability(
    nodes: list, edge_type: EdgeType
) -> None:
    """A cyclic path (a->b->a) backed by real edges both ways -> PASS reachability (S4).

    S4's guard is "every hop has a real edge", not "the path is acyclic" — a cycle
    whose every hop is a real edge is still a genuine walk in the graph.
    """
    a, b = (n.id for n in nodes)
    edges = [make_edge(a, b, edge_type, "high"), make_edge(b, a, edge_type, "high")]
    path = GroundTruthPath(
        id="path-cycle",
        severity="high",
        nodes=[a, b, a],
        edges=[f"{a}->{edge_type.value}->{b}", f"{b}->{edge_type.value}->{a}"],
        explanation="cyclic path with real backing edges",
    )
    outcomes = _outcomes(nodes, edges, path)
    assert outcomes["ground-truth path exists"] is Status.PASS  # S4: real hops, even if cyclic


@given(valid_node_lists(min_size=2, max_size=2), edge_types)
@settings(max_examples=_EXAMPLES, suppress_health_check=[HealthCheck.too_slow])
def test_cycle_missing_return_edge_fails_reachability(nodes: list, edge_type: EdgeType) -> None:
    """A claimed cycle a->b->a where the RETURN edge b->a does not exist -> FAIL (S4)."""
    a, b = (n.id for n in nodes)
    edges = [make_edge(a, b, edge_type, "high")]  # no b->a
    path = GroundTruthPath(
        id="path-broken-cycle",
        severity="high",
        nodes=[a, b, a],
        edges=[f"{a}->{edge_type.value}->{b}", f"{b}->{edge_type.value}->{a}"],
        explanation="claims a cycle but the return edge is missing",
    )
    outcomes = _outcomes(nodes, edges, path)
    assert outcomes["ground-truth path exists"] is Status.FAIL  # S4: missing hop


# --- wrong sink: path ends at a node with no stores_sensitive_data edge anywhere --


@given(valid_node_lists(min_size=3, max_size=3))
@settings(max_examples=_EXAMPLES, suppress_health_check=[HealthCheck.too_slow])
def test_path_to_wrong_sink_vacuously_passes_when_no_sink_declared(nodes: list) -> None:
    """A critical edge reaches a node with NO stores_sensitive_data edge anywhere -> vacuous PASS.

    S4 requires a critical edge to REACH a declared ``stores_sensitive_data`` sink;
    if no sink edge exists ANYWHERE in the graph, there is no sink claim to violate
    (graph_risk.py: `if not critical_edges or not sink_edges: return PASS`). This
    mirrors ``test_isolated_critical_sink_alone_passes`` from the other direction
    (critical edge present, sink absent) and locks in the same intentional vacuous-
    truth design — a "wrong sink" is only meaningfully wrong once a REAL sink exists
    elsewhere and is unreachable (see
    ``test_path_to_disconnected_sink_fails_critical_connectivity`` below).
    """
    a, b, c = (n.id for n in nodes)
    edges = [
        make_edge(a, b, EdgeType.CAN_READ, "critical"),
        make_edge(b, c, EdgeType.BELONGS_TO_APP, "low"),  # NOT stores_sensitive_data
    ]
    graph = ScenarioGraph(nodes=nodes, edges=edges)
    bundle = bundle_for(graph)
    engine = GraphRiskEngine(bundle, GENEROUS_SPEC)
    status = next(o.status for o in engine.run() if o.label == "critical-sink connectivity")
    assert status is Status.PASS  # S4: vacuous truth, no sink claim exists to violate


@given(valid_node_lists(min_size=4, max_size=4))
@settings(max_examples=_EXAMPLES, suppress_health_check=[HealthCheck.too_slow])
def test_path_to_disconnected_sink_fails_critical_connectivity(nodes: list) -> None:
    """A critical edge and a REAL sink edge exist, but on disjoint components -> FAIL (S4)."""
    a, b, c, d = (n.id for n in nodes)
    edges = [
        make_edge(a, b, EdgeType.CAN_READ, "critical"),
        make_edge(c, d, EdgeType.STORES_SENSITIVE_DATA, "critical"),  # unreachable from b
    ]
    graph = ScenarioGraph(nodes=nodes, edges=edges)
    bundle = bundle_for(graph)
    engine = GraphRiskEngine(bundle, GENEROUS_SPEC)
    status = next(o.status for o in engine.run() if o.label == "critical-sink connectivity")
    assert status is Status.FAIL  # S4: a real sink exists but is unreachable -> FAIL


# --- wrong start identity: path.nodes[0] is not where any critical edge originates -


@given(valid_node_lists(min_size=3, max_size=3), st.integers(min_value=0, max_value=2))
@settings(max_examples=_EXAMPLES, suppress_health_check=[HealthCheck.too_slow])
def test_ground_truth_reachable_but_wrong_start_still_needs_real_edges(
    nodes: list, start_index: int
) -> None:
    """A path declaring a start node with no outgoing edge to the next hop -> FAIL (S4).

    Picks an arbitrary "start" node (not necessarily node 0) and asserts a path
    that begins there with a fabricated next-hop (never actually connected) fails
    path-reachability regardless of which node is chosen as start.
    """
    ids = [n.id for n in nodes]
    start = ids[start_index]
    # no edges built in the graph at all -> any 2-hop path FAILs since no edge exists.
    graph = ScenarioGraph(nodes=nodes, edges=[])
    other = next(i for i in ids if i != start)
    path = GroundTruthPath(
        id="path-wrong-start",
        severity="high",
        nodes=[start, other],
        edges=[f"{start}->{EdgeType.CAN_READ.value}->{other}"],
        explanation="claims a hop from an arbitrary start with no real edge",
    )
    bundle = bundle_for(graph, ground_truth=GroundTruthPaths(paths=[path]))
    engine = GraphRiskEngine(bundle, GENEROUS_SPEC)
    status = next(o.status for o in engine.run() if o.label == "ground-truth path exists")
    assert status is Status.FAIL  # S4: no real edge from the declared start
