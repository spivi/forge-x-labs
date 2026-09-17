"""The local graph-risk engine (stdlib only).

Proves a generated scenario is self-consistent and safe:
  * every ground-truth node/edge exists in the graph,
  * each critical path is an actual walk in the graph,
  * a critical-risk edge reaches the declared target (the sink) of every path,
  * scenario constraints hold (resource budget, required counts),
  * no forbidden/destructive IAM permission appears (checked on the policy-node
    ``actions`` attributes — the graph is the source of truth),
  * each intentionally-broad grant is documented by an expected finding.
"""

from __future__ import annotations

import fnmatch
from collections import deque

from app.cloudforge import constants
from app.cloudforge.generate.base import ScenarioBundle
from app.cloudforge.generate.scale_profiles import SCALE_PROFILES
from app.cloudforge.models.graph import EdgeType, GraphEdge, GraphNode, NodeType
from app.cloudforge.models.scenario import ScenarioSpec
from app.cloudforge.validate.results import Status, ValidationOutcome


def _effective_budget(spec: ScenarioSpec) -> int:
    """Node budget = the larger of the spec's ``max_resources`` and the declared
    scale profile's ``max_nodes``.

    A composer-generated scenario declares a ``scale_profile`` whose band is the
    real budget authority (``medium`` legitimately holds 75-150 nodes), so the
    scale ceiling must not be capped by a small hand-authored ``max_resources``.
    An unknown profile name falls back to the spec's own budget."""
    profile = SCALE_PROFILES.get(spec.scale_profile)
    if profile is None:
        return spec.constraints.max_resources
    return max(spec.constraints.max_resources, profile.max_nodes)


class GraphRiskEngine:
    """Runs the stdlib-only integrity + safety checks over a scenario bundle."""

    def __init__(self, bundle: ScenarioBundle, spec: ScenarioSpec) -> None:
        self._bundle = bundle
        self._spec = spec
        self._node_ids = {n.id for n in bundle.graph.nodes}
        self._edge_keys = {e.key for e in bundle.graph.edges}

    def run(self) -> list[ValidationOutcome]:
        return [
            self._check_ground_truth_nodes(),
            self._check_ground_truth_edges(),
            self._check_finding_resources_exist(),
            self._check_paths_reachable(),
            self._check_critical_path_connectivity(),
            self._check_constraints(),
            self._check_forbidden_permissions(),
            self._check_broad_grants_documented(),
        ]

    def _check_ground_truth_nodes(self) -> ValidationOutcome:
        referenced = {nid for p in self._bundle.ground_truth.paths for nid in p.nodes}
        missing = referenced - self._node_ids
        if missing:
            return ValidationOutcome(
                Status.FAIL, "ground-truth nodes exist", f"missing: {sorted(missing)}"
            )
        return ValidationOutcome(Status.PASS, "ground-truth nodes exist")

    def _check_ground_truth_edges(self) -> ValidationOutcome:
        referenced = {ek for p in self._bundle.ground_truth.paths for ek in p.edges}
        missing = referenced - self._edge_keys
        if missing:
            return ValidationOutcome(
                Status.FAIL, "ground-truth edges exist", f"missing: {sorted(missing)}"
            )
        return ValidationOutcome(Status.PASS, "ground-truth edges exist")

    def _check_finding_resources_exist(self) -> ValidationOutcome:
        for finding in self._bundle.findings.findings:
            for rid in finding.resource_ids:
                if rid not in self._node_ids:
                    return ValidationOutcome(
                        Status.FAIL,
                        "expected findings reference real resources",
                        f"{finding.id} references missing resource {rid}",
                    )
        return ValidationOutcome(Status.PASS, "expected findings reference real resources")

    def _check_paths_reachable(self) -> ValidationOutcome:
        for path in self._bundle.ground_truth.paths:
            for src, dst in zip(path.nodes, path.nodes[1:], strict=False):
                if not self._has_any_edge(src, dst):
                    return ValidationOutcome(
                        Status.FAIL,
                        "ground-truth path exists",
                        f"no edge {src}->{dst} in {path.id}",
                    )
        return ValidationOutcome(Status.PASS, "ground-truth path exists")

    def _has_any_edge(self, src: str, dst: str) -> bool:
        return any(e.from_ == src and e.to == dst for e in self._bundle.graph.edges)

    def _check_critical_path_connectivity(self) -> ValidationOutcome:
        """Family-agnostic check: a critical-risk edge must reach the declared
        target of every ground-truth path (the sink the path says the attacker
        reaches, whatever its type). A bundle whose paths declare no target (an
        old pack, or a graph with no paths at all) falls back to the original
        rule: some critical edge must reach some ``stores_sensitive_data`` sink.
        The sink edge itself never counts as the critical edge."""
        critical_edges = [
            e
            for e in self._bundle.graph.edges
            if e.security.risk == "critical" and e.type != EdgeType.STORES_SENSITIVE_DATA
        ]
        targets = [p.target for p in self._bundle.ground_truth.paths if p.target]
        if targets:
            return self._check_targets_reached(critical_edges, targets)
        sink_edges = [
            e for e in self._bundle.graph.edges if e.type == EdgeType.STORES_SENSITIVE_DATA
        ]
        if not critical_edges or not sink_edges:
            return ValidationOutcome(Status.PASS, "critical-sink connectivity")
        sinks = [e.to for e in sink_edges]
        if any(self._can_reach(e.to, sink) for e in critical_edges for sink in sinks):
            return ValidationOutcome(Status.PASS, "critical-sink connectivity")
        return ValidationOutcome(
            Status.FAIL,
            "critical-sink connectivity",
            "critical-risk edge cannot reach stores_sensitive_data sink",
        )

    def _check_targets_reached(
        self, critical_edges: list[GraphEdge], targets: list[str]
    ) -> ValidationOutcome:
        for target in targets:
            if not any(self._can_reach(e.to, target) for e in critical_edges):
                return ValidationOutcome(
                    Status.FAIL,
                    "critical-sink connectivity",
                    f"no critical-risk edge reaches declared target {target}",
                )
        return ValidationOutcome(Status.PASS, "critical-sink connectivity")

    def _can_reach(self, src: str, dst: str) -> bool:
        """BFS to check if src can reach dst in the graph."""
        if src == dst:
            return True

        visited = {src}
        queue = deque([src])

        while queue:
            node = queue.popleft()
            for edge in self._bundle.graph.edges:
                if edge.from_ == node and edge.to not in visited:
                    if edge.to == dst:
                        return True
                    visited.add(edge.to)
                    queue.append(edge.to)

        return False

    def _check_constraints(self) -> ValidationOutcome:
        node_count = len(self._bundle.graph.nodes)
        budget = _effective_budget(self._spec)
        if node_count > budget:
            return ValidationOutcome(
                Status.FAIL, "resource budget respected", f"{node_count} nodes > max {budget}"
            )
        want = self._spec.requirements.critical_chains
        have = sum(1 for p in self._bundle.ground_truth.paths if p.severity == "critical")
        if have < want:
            return ValidationOutcome(
                Status.FAIL,
                "critical-chain count met",
                f"want {want} critical path(s), have {have}",
            )
        return ValidationOutcome(Status.PASS, "scenario constraints satisfied")

    def _check_forbidden_permissions(self) -> ValidationOutcome:
        for node in self._policy_nodes():
            for action in _actions_of(node):
                pattern = _matched_forbidden(action)
                if pattern is not None:
                    return ValidationOutcome(
                        Status.FAIL,
                        "no forbidden permissions",
                        f"{node.id} grants {action} (matches {pattern})",
                    )
        return ValidationOutcome(Status.PASS, "no forbidden permissions")

    def _check_broad_grants_documented(self) -> ValidationOutcome:
        documented = {rid for f in self._bundle.findings.findings for rid in f.resource_ids}
        for node in self._policy_nodes():
            if _has_broad_grant(node) and node.id not in documented:
                return ValidationOutcome(
                    Status.FAIL, "broad grants documented", f"{node.id} broad grant has no finding"
                )
        return ValidationOutcome(Status.PASS, "broad grants documented by findings")

    def _policy_nodes(self) -> list[GraphNode]:
        return [n for n in self._bundle.graph.nodes if n.type is NodeType.IAM_POLICY]


def _actions_of(node: GraphNode) -> list[str]:
    raw = node.attributes.get("actions", [])
    return raw if isinstance(raw, list) else [raw]


def _matched_forbidden(action: str) -> str | None:
    for pattern in constants.FORBIDDEN_PERMISSION_PATTERNS:
        if fnmatch.fnmatch(action, pattern):
            return pattern
    return None


def _has_broad_grant(node: GraphNode) -> bool:
    actions = _actions_of(node)
    return any(
        fnmatch.fnmatch(action, pattern)
        for action in actions
        for pattern in constants.ALLOWED_BROAD_PATTERNS
    )
