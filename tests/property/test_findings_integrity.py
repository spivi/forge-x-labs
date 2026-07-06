"""Property tests: expected findings integrity (S5 / S6 / S7).

* S5: no expected finding references a missing resource.
* S6: no broad grant exists without a documented expected finding.
* S7: no destructive permission survives validation.

Stresses ``GraphRiskEngine._check_broad_grants_documented`` and
``_check_forbidden_permissions`` plus the ``ExpectedFinding`` model itself (missing/
duplicate ids, unknown family, wrong severity) via Hypothesis-generated policy nodes
and finding sets. Every assertion is commented with the clause it proves.
"""

from __future__ import annotations

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from app.cloudforge.models.findings import ExpectedFinding, ExpectedFindings, FindingFamily
from app.cloudforge.models.graph import GraphNode, NodeSecurity, NodeTags, NodeType, ScenarioGraph
from app.cloudforge.validate.graph_risk import GraphRiskEngine
from app.cloudforge.validate.results import Status
from tests.property.strategies import (
    GENEROUS_SPEC,
    bundle_for,
    finding_ids,
    scanner_visibilities,
    severities,
)

_EXAMPLES = 500

_TAGS = NodeTags(env="test", owner="prop-team", app="prop-app")

_FORBIDDEN_CONCRETE = (
    "iam:DeleteRole",
    "iam:DeleteUser",
    "s3:DeleteBucket",
    "ec2:TerminateInstances",
    "kms:ScheduleKeyDeletion",
    "organizations:CreateAccount",
    "organizations:LeaveOrganization",
)
_ALLOWED_BROAD_CONCRETE = (
    "s3:GetObject",
    "s3:GetBucketAcl",
    "s3:ListBucket",
    "s3:ListAllMyBuckets",
)
_BENIGN_ACTIONS = ("s3:PutObject", "iam:GetRole", "logs:CreateLogGroup", "ec2:DescribeInstances")

forbidden_actions = st.sampled_from(_FORBIDDEN_CONCRETE)
broad_actions = st.sampled_from(_ALLOWED_BROAD_CONCRETE)
benign_actions = st.sampled_from(_BENIGN_ACTIONS)


def _policy_node(node_id: str, actions: list[str]) -> GraphNode:
    return GraphNode(
        id=node_id,
        type=NodeType.IAM_POLICY,
        name=f"policy-{node_id}",
        tags=_TAGS,
        security=NodeSecurity(criticality="high"),
        attributes={"actions": actions},
    )


def _outcome(graph: ScenarioGraph, findings: ExpectedFindings, label_prefix: str) -> Status:
    """Look up an outcome by label PREFIX.

    ``GraphRiskEngine._check_broad_grants_documented`` uses two different exact
    labels for its FAIL ("broad grants documented") vs. PASS ("broad grants
    documented by findings") branches of the SAME check — a label match must use a
    prefix, not equality, to find both. Cosmetic (not a clause violation): the
    ``label`` is a check name, and both strings share the "broad grants documented"
    prefix, so a caller keying on a single canonical label sees one check either way.
    """
    bundle = bundle_for(graph, findings=findings)
    engine = GraphRiskEngine(bundle, GENEROUS_SPEC)
    return next(o.status for o in engine.run() if o.label.startswith(label_prefix))


# --- S7: any forbidden/destructive permission FAILs, regardless of findings -------


@given(forbidden_actions, st.lists(benign_actions, max_size=3))
@settings(max_examples=_EXAMPLES, suppress_health_check=[HealthCheck.too_slow])
def test_forbidden_permission_always_fails(forbidden: str, extra_benign: list[str]) -> None:
    """A forbidden pattern anywhere in policy actions -> FAIL, findings notwithstanding (S7)."""
    node = _policy_node("pol-1", [forbidden, *extra_benign])
    graph = ScenarioGraph(nodes=[node], edges=[])
    # Even a fully-documented finding covering this exact resource cannot rescue a
    # forbidden permission — S7 is absolute.
    finding = ExpectedFinding(
        id="f-1",
        severity="critical",
        family=FindingFamily.IAM_EXCESSIVE_PRIVILEGE,
        resource_ids=["pol-1"],
        expected_scanner_visibility="visible",
        ground_truth="documented anyway",
        remediation="remove it",
    )
    status = _outcome(graph, ExpectedFindings(findings=[finding]), "no forbidden permissions")
    assert status is Status.FAIL  # S7: forbidden perm always FAILs


@given(st.lists(benign_actions, min_size=0, max_size=5))
@settings(max_examples=_EXAMPLES, suppress_health_check=[HealthCheck.too_slow])
def test_no_forbidden_permission_passes(benign: list[str]) -> None:
    """Only benign actions on every policy node -> no forbidden-permission FAIL (S7)."""
    node = _policy_node("pol-1", benign)
    graph = ScenarioGraph(nodes=[node], edges=[])
    status = _outcome(graph, ExpectedFindings(findings=[]), "no forbidden permissions")
    assert status is Status.PASS  # S7: nothing forbidden present


# --- S6: a broad grant with NO documenting finding FAILs; documented -> PASS ------


@given(broad_actions)
@settings(max_examples=_EXAMPLES, suppress_health_check=[HealthCheck.too_slow])
def test_broad_grant_without_finding_fails(broad: str) -> None:
    """A broad s3:Get*/List* grant with no expected finding referencing it -> FAIL (S6)."""
    node = _policy_node("pol-broad", [broad])
    graph = ScenarioGraph(nodes=[node], edges=[])
    status = _outcome(graph, ExpectedFindings(findings=[]), "broad grants documented")
    assert status is Status.FAIL  # S6: undocumented broad grant


@given(broad_actions, finding_ids, severities, scanner_visibilities)
@settings(max_examples=_EXAMPLES, suppress_health_check=[HealthCheck.too_slow])
def test_broad_grant_with_documenting_finding_passes(
    broad: str, fid: str, severity: str, visibility: str
) -> None:
    """A broad grant referenced by SOME finding's resource_ids -> PASS (S6)."""
    node = _policy_node("pol-broad", [broad])
    graph = ScenarioGraph(nodes=[node], edges=[])
    finding = ExpectedFinding(
        id=fid,
        severity=severity,  # type: ignore[arg-type]
        family=FindingFamily.IAM_EXCESSIVE_PRIVILEGE,
        resource_ids=["pol-broad"],
        expected_scanner_visibility=visibility,  # type: ignore[arg-type]
        ground_truth="documented broad grant",
        remediation="tighten scope",
    )
    status = _outcome(graph, ExpectedFindings(findings=[finding]), "broad grants documented")
    assert status is Status.PASS  # S6: documented broad grant


@given(broad_actions, finding_ids)
@settings(max_examples=_EXAMPLES, suppress_health_check=[HealthCheck.too_slow])
def test_broad_grant_documented_for_wrong_resource_still_fails(broad: str, fid: str) -> None:
    """A finding exists, but its resource_ids do NOT include the broad-grant node -> FAIL (S6)."""
    node = _policy_node("pol-broad", [broad])
    other_node = _policy_node("pol-other", [])
    graph = ScenarioGraph(nodes=[node, other_node], edges=[])
    finding = ExpectedFinding(
        id=fid,
        severity="medium",
        family=FindingFamily.IAM_EXCESSIVE_PRIVILEGE,
        resource_ids=["pol-other"],  # wrong resource — does not document pol-broad
        expected_scanner_visibility="visible",
        ground_truth="documents the wrong node",
        remediation="n/a",
    )
    status = _outcome(graph, ExpectedFindings(findings=[finding]), "broad grants documented")
    assert status is Status.FAIL  # S6: broad grant on pol-broad remains undocumented


# --- S5: findings referencing a resource id NOT in the graph -----------------------
#
# NOTE: `_check_broad_grants_documented` and `_check_forbidden_permissions` never
# themselves validate that `finding.resource_ids` point at real graph nodes — S5 as
# currently enforced by `GraphRiskEngine` only reconciles ground-truth-PATH node/edge
# ids (`_check_ground_truth_nodes` / `_check_ground_truth_edges`), not
# `ExpectedFinding.resource_ids`. This is exercised below: it demonstrates a REAL
# invariant gap. See BUGS FOUND in the result report.


@pytest.mark.xfail(
    strict=True,
    reason=(
        "BUG: S5 — GraphRiskEngine.run() has NO check reconciling "
        "ExpectedFinding.resource_ids against real graph node ids; a finding "
        "referencing a nonexistent resource passes validation with zero FAILs."
    ),
)
@given(
    finding_ids,
    severities,
    scanner_visibilities,
    st.text(alphabet=st.characters(whitelist_categories=("Ll", "Nd")), min_size=1, max_size=10),
)
@settings(max_examples=_EXAMPLES, suppress_health_check=[HealthCheck.too_slow])
def test_finding_referencing_missing_resource_should_fail_graph_risk(
    fid: str, severity: str, visibility: str, ghost_id: str
) -> None:
    """S5: a finding referencing a resource id absent from the graph must FAIL validation.

    BUG (S5): minimal reproducer — a graph with one real node ``pol-real`` and NO
    other nodes; an ``ExpectedFinding`` whose ``resource_ids`` names a node id that
    was never built (e.g. ``ghost-xyz``). The correct behavior per S5 ("No expected
    finding references a missing resource") is that ``GraphRiskEngine.run()`` FAILs.
    Instead, ALL 7 checks in ``GraphRiskEngine.run()`` PASS — there is no check that
    reconciles ``self._bundle.findings.findings[*].resource_ids`` against
    ``self._node_ids`` (the engine only reconciles ground-truth-PATH node/edge ids,
    never finding resource ids). Wrong: no FAIL is raised. Expected: a FAIL outcome
    (e.g. "finding resources exist") naming the missing resource id.
    """
    ghost = f"ghost-{ghost_id}"
    node = _policy_node("pol-real", [])
    graph = ScenarioGraph(nodes=[node], edges=[])
    if ghost in {n.id for n in graph.nodes}:
        return
    finding = ExpectedFinding(
        id=fid,
        severity=severity,  # type: ignore[arg-type]
        family=FindingFamily.IAM_EXCESSIVE_PRIVILEGE,
        resource_ids=[ghost],
        expected_scanner_visibility=visibility,  # type: ignore[arg-type]
        ground_truth="references a resource that does not exist",
        remediation="n/a",
    )
    bundle = bundle_for(graph, findings=ExpectedFindings(findings=[finding]))
    engine = GraphRiskEngine(bundle, GENEROUS_SPEC)
    outcomes = engine.run()
    # S5: a finding referencing a missing resource MUST produce a FAIL somewhere.
    assert any(o.status is Status.FAIL for o in outcomes), (
        f"S5 VIOLATION: finding {fid!r} references missing resource {ghost!r} "
        "but GraphRiskEngine reported no FAIL"
    )


# --- ExpectedFinding model-level integrity: missing/duplicate ids, unknown family --


@given(st.lists(finding_ids, min_size=2, max_size=2, unique=False))
@settings(max_examples=_EXAMPLES, suppress_health_check=[HealthCheck.too_slow])
def test_duplicate_finding_ids_not_rejected_by_model(ids: list[str]) -> None:
    """Baseline: ``ExpectedFindings`` does not enforce unique finding ids at the model layer.

    Not a listed clause violation — S5/S6/S7 are about resource references and
    forbidden/broad grants, not id uniqueness. Documents current behavior as a
    baseline (see BUGS FOUND for the reconciliation gap, which is a real issue;
    this one is a plain absence of a constraint, not a broken guarantee).
    """
    dup_id = ids[0]
    findings = [
        ExpectedFinding(
            id=dup_id,
            severity="low",
            family=FindingFamily.IAM_EXCESSIVE_PRIVILEGE,
            resource_ids=["whatever"],
            expected_scanner_visibility="visible",
            ground_truth="first",
            remediation="n/a",
        ),
        ExpectedFinding(
            id=dup_id,
            severity="low",
            family=FindingFamily.IAM_EXCESSIVE_PRIVILEGE,
            resource_ids=["whatever"],
            expected_scanner_visibility="visible",
            ground_truth="second, duplicate id",
            remediation="n/a",
        ),
    ]
    bundle_findings = ExpectedFindings(findings=findings)
    assert len(bundle_findings.findings) == 2  # documented baseline, not a contract clause


@given(st.text(min_size=1, max_size=30))
@settings(max_examples=_EXAMPLES, suppress_health_check=[HealthCheck.too_slow])
def test_unknown_finding_family_rejected_by_enum(raw_family: str) -> None:
    """An unknown ``family`` string is rejected by the FindingFamily enum (S5/S6 precondition)."""
    known = {f.value for f in FindingFamily}
    if raw_family in known:
        finding = ExpectedFinding(
            id="f-x",
            severity="low",
            family=raw_family,  # type: ignore[arg-type]
            resource_ids=["r-1"],
            expected_scanner_visibility="visible",
            ground_truth="ok",
            remediation="n/a",
        )
        assert finding.family.value == raw_family
        return
    try:
        ExpectedFinding(
            id="f-x",
            severity="low",
            family=raw_family,  # type: ignore[arg-type]
            resource_ids=["r-1"],
            expected_scanner_visibility="visible",
            ground_truth="ok",
            remediation="n/a",
        )
    except ValidationError:
        return  # rejected: unknown family
    raise AssertionError(f"unknown finding family {raw_family!r} incorrectly accepted")


@given(st.text(min_size=1, max_size=20))
@settings(max_examples=_EXAMPLES, suppress_health_check=[HealthCheck.too_slow])
def test_wrong_severity_rejected_by_literal(raw_severity: str) -> None:
    """A ``severity`` outside {low, medium, high, critical} is rejected (S5/S6 precondition)."""
    known = {"low", "medium", "high", "critical"}
    if raw_severity in known:
        finding = ExpectedFinding(
            id="f-y",
            severity=raw_severity,  # type: ignore[arg-type]
            family=FindingFamily.IAM_EXCESSIVE_PRIVILEGE,
            resource_ids=["r-1"],
            expected_scanner_visibility="visible",
            ground_truth="ok",
            remediation="n/a",
        )
        assert finding.severity == raw_severity
        return
    try:
        ExpectedFinding(
            id="f-y",
            severity=raw_severity,  # type: ignore[arg-type]
            family=FindingFamily.IAM_EXCESSIVE_PRIVILEGE,
            resource_ids=["r-1"],
            expected_scanner_visibility="visible",
            ground_truth="ok",
            remediation="n/a",
        )
    except ValidationError:
        return  # rejected: wrong severity
    raise AssertionError(f"invalid severity {raw_severity!r} incorrectly accepted")


# --- combined S6+S7 fuzz: any mix of forbidden + broad + benign actions ------------


@given(
    st.lists(st.one_of(forbidden_actions, broad_actions, benign_actions), min_size=0, max_size=6),
)
@settings(max_examples=_EXAMPLES, suppress_health_check=[HealthCheck.too_slow])
def test_mixed_actions_forbidden_dominates_regardless_of_broad_documentation(
    actions: list[str],
) -> None:
    """Any mix of actions: if a forbidden pattern is present, forbidden-check FAILs;
    a broad grant with no finding also independently FAILs its own check (S6+S7).
    """
    node = _policy_node("pol-mix", actions)
    graph = ScenarioGraph(nodes=[node], edges=[])
    has_forbidden = any(a in _FORBIDDEN_CONCRETE for a in actions)
    has_broad = any(a in _ALLOWED_BROAD_CONCRETE for a in actions)

    bundle = bundle_for(graph, findings=ExpectedFindings(findings=[]))
    engine = GraphRiskEngine(bundle, GENEROUS_SPEC)
    outcomes = list(engine.run())
    forbidden_status = next(o.status for o in outcomes if o.label == "no forbidden permissions")
    # See `_outcome`'s docstring: the broad-grants check uses two different exact
    # labels for its FAIL vs. PASS branches — match by prefix.
    broad_status = next(
        o.status for o in outcomes if o.label.startswith("broad grants documented")
    )

    if has_forbidden:
        assert forbidden_status is Status.FAIL  # S7
    else:
        assert forbidden_status is Status.PASS  # S7

    if has_broad:
        assert broad_status is Status.FAIL  # S6 (undocumented)
    else:
        assert broad_status is Status.PASS  # S6
