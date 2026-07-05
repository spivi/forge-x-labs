"""The local graph-risk engine (stdlib only).

Proves a generated scenario is self-consistent and safe:
  * every ground-truth node/edge exists in the graph,
  * each critical path is an actual walk in the graph,
  * scenario constraints hold (resource budget, required counts),
  * no forbidden/destructive IAM permission appears (checked on the policy-node
    ``actions`` attributes — the graph is the source of truth),
  * each intentionally-broad grant is documented by an expected finding.
"""

from __future__ import annotations

import fnmatch

from app.cloudforge import constants
from app.cloudforge.generate.base import ScenarioBundle
from app.cloudforge.models.graph import GraphNode, NodeType
from app.cloudforge.models.scenario import ScenarioSpec
from app.cloudforge.validate.results import Status, ValidationOutcome


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
            self._check_paths_reachable(),
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

    def _check_constraints(self) -> ValidationOutcome:
        node_count = len(self._bundle.graph.nodes)
        budget = self._spec.constraints.max_resources
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
