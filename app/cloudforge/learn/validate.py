"""Graph-fragment validation rules (design §9.2).

A ``RiskPattern.graph_fragment`` is valid only if all four rules hold:

1. **Endpoints resolve** — every edge ``from``/``to`` references a node in the
   fragment. ``ScenarioGraph``'s own ``model_validator`` already enforces this at
   construction time; we surface it here explicitly so a dangling-edge fragment is
   reported as an invalid *pattern*, not just an unconstructible graph.
2. **Node/edge types known-or-generic** — every node/edge ``type`` is a member of
   the existing ``NodeType``/``EdgeType`` enums (the only documented generic
   placeholders, e.g. ``NodeType.APPLICATION``, live inside those enums too).
   Unknown/undocumented types fail. Because ``GraphNode.type``/``GraphEdge.type``
   are themselves typed as those enums, a constructed fragment already satisfies
   this — the check exists to surface the rule explicitly and stay correct if that
   ever changes.
3. **Findings reference existing resources** — every ``ExpectedFinding.resource_ids``
   entry points to a node in the fragment (mirrors FXL-D003 point 4).
4. **No forbidden destructive actions** — reuses ``constants.FORBIDDEN_PERMISSION_PATTERNS``
   (the same fnmatch scan as ``validate.graph_risk``) over every node's ``actions``
   attribute. Any match fails validation AND forces
   ``safety_classification = unsafe_operational`` (rejected). Broad *read* grants are
   allowed, mirroring the generator's risk engine.

``validate_fragment`` is deterministic and never mutates its input; it returns a new
``RiskPattern`` with ``validation_status`` (and, on a rule-4 failure,
``safety_classification``) set.
"""

from __future__ import annotations

import fnmatch

from app.cloudforge import constants
from app.cloudforge.learn.pattern_enums import SafetyClassification, ValidationStatus
from app.cloudforge.learn.pattern_models import RiskPattern
from app.cloudforge.models.graph import EdgeType, GraphNode, NodeType, ScenarioGraph


def validate_fragment(pattern: RiskPattern) -> RiskPattern:
    """Validate ``pattern.graph_fragment`` against the design §9.2 rules.

    Returns a copy of ``pattern`` with ``validation_status`` set to ``valid`` (all
    four rules pass) or ``invalid`` (at least one fails). A forbidden-permission
    failure additionally forces ``safety_classification = unsafe_operational``.
    """
    reasons = _failure_reasons(pattern)
    if not reasons:
        return pattern.model_copy(update={"validation_status": ValidationStatus.VALID})

    updates: dict[str, object] = {"validation_status": ValidationStatus.INVALID}
    if _has_forbidden_permission(pattern.graph_fragment):
        updates["safety_classification"] = SafetyClassification.UNSAFE_OPERATIONAL
    return pattern.model_copy(update=updates)


def validation_reasons(pattern: RiskPattern) -> list[str]:
    """Return the human-readable reasons ``pattern`` fails validation (empty if valid)."""
    return _failure_reasons(pattern)


def _failure_reasons(pattern: RiskPattern) -> list[str]:
    fragment = pattern.graph_fragment
    reasons: list[str] = []
    reasons.extend(_dangling_edge_reasons(fragment))
    reasons.extend(_unknown_type_reasons(fragment))
    reasons.extend(_missing_finding_resource_reasons(pattern))
    reasons.extend(_forbidden_permission_reasons(fragment))
    return reasons


# --- rule 1: edge endpoints resolve ---------------------------------------------


def _dangling_edge_reasons(fragment: ScenarioGraph) -> list[str]:
    """Surface dangling edges explicitly (``ScenarioGraph`` already forbids them)."""
    node_ids = {node.id for node in fragment.nodes}
    reasons = []
    for edge in fragment.edges:
        missing = {edge.from_, edge.to} - node_ids
        if missing:
            reasons.append(f"edge {edge.key} references unknown node(s): {sorted(missing)}")
    return reasons


# --- rule 2: node/edge types known-or-generic -----------------------------------


def _unknown_type_reasons(fragment: ScenarioGraph) -> list[str]:
    reasons = []
    for node in fragment.nodes:
        if node.type not in NodeType:
            reasons.append(f"node {node.id} has unknown type: {node.type!r}")
    for edge in fragment.edges:
        if edge.type not in EdgeType:
            reasons.append(f"edge {edge.key} has unknown type: {edge.type!r}")
    return reasons


# --- rule 3: findings reference existing resources ------------------------------


def _missing_finding_resource_reasons(pattern: RiskPattern) -> list[str]:
    node_ids = {node.id for node in pattern.graph_fragment.nodes}
    reasons = []
    for finding in pattern.expected_findings:
        missing = sorted(set(finding.resource_ids) - node_ids)
        if missing:
            reasons.append(f"finding {finding.id} references unknown resource(s): {missing}")
    return reasons


# --- rule 4: no forbidden destructive actions -----------------------------------


def _forbidden_permission_reasons(fragment: ScenarioGraph) -> list[str]:
    reasons = []
    for node in fragment.nodes:
        for action in _actions_of(node):
            pattern_matched = _matched_forbidden(action)
            if pattern_matched is not None:
                reasons.append(f"{node.id} grants {action} (matches {pattern_matched})")
    return reasons


def _has_forbidden_permission(fragment: ScenarioGraph) -> bool:
    return bool(_forbidden_permission_reasons(fragment))


def _actions_of(node: GraphNode) -> list[str]:
    raw = node.attributes.get("actions", [])
    return raw if isinstance(raw, list) else [raw]


def _matched_forbidden(action: str) -> str | None:
    for pattern in constants.FORBIDDEN_PERMISSION_PATTERNS:
        if fnmatch.fnmatch(action, pattern):
            return pattern
    return None
