"""``validate_fragment`` tests: the 4 graph-fragment validation rules (§9.2).

Exercises each rule's pass/fail path against hand-built ``RiskPattern``s for precise
control over inputs, plus real normalizer/adapter output (the seed rule catalog and a
``cloudforge_scenario`` fixture dir) so "a clean normalized pattern is valid" is proven
against real data, not a hand-waved fixture.
"""

from __future__ import annotations

from pathlib import Path

from app.cloudforge.learn.adapters.cloudforge_scenario import CloudforgeScenarioAdapter
from app.cloudforge.learn.adapters.rule_catalog_yaml import RuleCatalogYamlAdapter
from app.cloudforge.learn.normalizer import PatternNormalizer
from app.cloudforge.learn.pattern_enums import SafetyClassification, ValidationStatus
from app.cloudforge.learn.registry import load_registry
from app.cloudforge.learn.source_models import ReuseStatus, SourceEntry, SourceType
from app.cloudforge.learn.validate import validate_fragment, validation_reasons
from app.cloudforge.models.findings import ExpectedFinding, FindingFamily
from app.cloudforge.models.graph import (
    EdgeSecurity,
    GraphEdge,
    GraphNode,
    NodeSecurity,
    NodeTags,
    NodeType,
    ScenarioGraph,
)

from .conftest import build_fragment, build_pattern

_FIXTURES = Path("tests/cloudforge/learn/fixtures")
_CI_CD_DIR = _FIXTURES / "scenario_ci_cd_iam_chain"
_REGISTRY = Path("data/source_registry.yaml")

_TAGS = NodeTags(env="prod", owner="team", app="analytics")
_SECURITY = NodeSecurity(criticality="medium")


def _node(node_id: str, node_type: NodeType = NodeType.APPLICATION, **attrs: object) -> GraphNode:
    return GraphNode(
        id=node_id, type=node_type, name=node_id, tags=_TAGS, security=_SECURITY, attributes=attrs
    )


def _policy_node(node_id: str, actions: list[str]) -> GraphNode:
    return _node(node_id, NodeType.IAM_POLICY, actions=actions)


# --- rule 1: edge endpoints resolve ---------------------------------------------


class TestEdgeEndpointsResolve:
    def test_clean_fragment_with_valid_edges_passes(self) -> None:
        pattern = build_pattern()
        result = validate_fragment(pattern)
        assert result.validation_status is ValidationStatus.VALID

    def test_dangling_edge_cannot_even_be_constructed_but_check_still_reports_none(self) -> None:
        # ScenarioGraph's own model_validator forbids dangling edges at construction,
        # so any real fragment passed in already satisfies rule 1 -- this proves the
        # explicit check does not false-positive on a normal, edge-having fragment.
        fragment = build_fragment()
        assert not any("unknown node" in r for r in _reasons_for_fragment(fragment))


def _reasons_for_fragment(fragment: ScenarioGraph) -> list[str]:
    pattern = build_pattern()
    updated = pattern.model_copy(update={"graph_fragment": fragment, "expected_findings": []})
    return validation_reasons(updated)


# --- rule 2: node/edge types known-or-generic -----------------------------------


class TestTypesKnownOrGeneric:
    def test_all_known_node_and_edge_types_pass(self) -> None:
        fragment = ScenarioGraph(
            nodes=[_node("n1", NodeType.APPLICATION), _node("n2", NodeType.S3_BUCKET)],
            edges=[
                GraphEdge(
                    **{"from": "n1", "to": "n2"},
                    type="can_read",
                    security=EdgeSecurity(risk="low"),
                )
            ],
        )
        reasons = _reasons_for_fragment(fragment)
        assert reasons == []

    def test_generic_application_placeholder_node_passes(self) -> None:
        # The normalizer's minimal-fragment builder uses NodeType.APPLICATION as its
        # documented generic placeholder for a bare resource-type list.
        fragment = ScenarioGraph(nodes=[_node("resource-0", NodeType.APPLICATION)], edges=[])
        assert _reasons_for_fragment(fragment) == []


# --- rule 3: findings reference existing resources ------------------------------


class TestFindingsReferenceExistingResources:
    def test_finding_referencing_real_node_passes(self) -> None:
        pattern = build_pattern()
        result = validate_fragment(pattern)
        assert result.validation_status is ValidationStatus.VALID

    def test_finding_referencing_missing_node_is_invalid(self) -> None:
        pattern = build_pattern()
        bad_finding = ExpectedFinding(
            id="f-bad",
            severity="high",
            family=FindingFamily.S3_PUBLIC_EXPOSURE,
            resource_ids=["does-not-exist"],
            expected_scanner_visibility="visible",
            ground_truth="bogus",
            remediation="n/a",
        )
        pattern = pattern.model_copy(update={"expected_findings": [bad_finding]})

        result = validate_fragment(pattern)

        assert result.validation_status is ValidationStatus.INVALID
        reasons = validation_reasons(pattern)
        assert any("f-bad" in r and "does-not-exist" in r for r in reasons)

    def test_no_findings_at_all_passes_rule_3(self) -> None:
        pattern = build_pattern().model_copy(update={"expected_findings": []})
        result = validate_fragment(pattern)
        assert result.validation_status is ValidationStatus.VALID


# --- rule 4: no forbidden destructive actions -----------------------------------


class TestNoForbiddenDestructiveActions:
    def test_clean_policy_actions_pass(self) -> None:
        fragment = ScenarioGraph(
            nodes=[_policy_node("pol-1", ["s3:GetObject", "s3:ListBucket"])], edges=[]
        )
        pattern = build_pattern().model_copy(
            update={"graph_fragment": fragment, "expected_findings": []}
        )
        result = validate_fragment(pattern)
        assert result.validation_status is ValidationStatus.VALID

    def test_forbidden_iam_delete_action_is_invalid_and_unsafe(self) -> None:
        fragment = ScenarioGraph(
            nodes=[_policy_node("pol-1", ["iam:DeleteRole"])],
            edges=[],
        )
        pattern = build_pattern().model_copy(
            update={"graph_fragment": fragment, "expected_findings": []}
        )

        result = validate_fragment(pattern)

        assert result.validation_status is ValidationStatus.INVALID
        assert result.safety_classification is SafetyClassification.UNSAFE_OPERATIONAL

    def test_forbidden_s3_delete_bucket_action_is_invalid(self) -> None:
        fragment = ScenarioGraph(nodes=[_policy_node("pol-1", ["s3:DeleteBucket"])], edges=[])
        pattern = build_pattern().model_copy(
            update={"graph_fragment": fragment, "expected_findings": []}
        )
        result = validate_fragment(pattern)
        assert result.validation_status is ValidationStatus.INVALID

    def test_forbidden_ec2_terminate_instances_action_is_invalid(self) -> None:
        fragment = ScenarioGraph(
            nodes=[_policy_node("pol-1", ["ec2:TerminateInstances"])], edges=[]
        )
        pattern = build_pattern().model_copy(
            update={"graph_fragment": fragment, "expected_findings": []}
        )
        result = validate_fragment(pattern)
        assert result.validation_status is ValidationStatus.INVALID

    def test_forbidden_kms_schedule_key_deletion_action_is_invalid(self) -> None:
        fragment = ScenarioGraph(
            nodes=[_policy_node("pol-1", ["kms:ScheduleKeyDeletion"])], edges=[]
        )
        pattern = build_pattern().model_copy(
            update={"graph_fragment": fragment, "expected_findings": []}
        )
        result = validate_fragment(pattern)
        assert result.validation_status is ValidationStatus.INVALID

    def test_forbidden_organizations_wildcard_action_is_invalid(self) -> None:
        fragment = ScenarioGraph(
            nodes=[_policy_node("pol-1", ["organizations:LeaveOrganization"])], edges=[]
        )
        pattern = build_pattern().model_copy(
            update={"graph_fragment": fragment, "expected_findings": []}
        )
        result = validate_fragment(pattern)
        assert result.validation_status is ValidationStatus.INVALID

    def test_broad_read_grant_is_allowed(self) -> None:
        fragment = ScenarioGraph(nodes=[_policy_node("pol-1", ["s3:Get*", "s3:List*"])], edges=[])
        pattern = build_pattern().model_copy(
            update={"graph_fragment": fragment, "expected_findings": []}
        )
        result = validate_fragment(pattern)
        assert result.validation_status is ValidationStatus.VALID

    def test_forbidden_action_does_not_clobber_unrelated_safety_classification_on_pass(
        self,
    ) -> None:
        pattern = build_pattern(safety_classification=SafetyClassification.DEFENSIVE_PATTERN)
        result = validate_fragment(pattern)
        assert result.safety_classification is SafetyClassification.DEFENSIVE_PATTERN


# --- overall status / determinism / non-mutation --------------------------------


class TestOverallStatusAndDeterminism:
    def test_valid_pattern_becomes_valid(self) -> None:
        pattern = build_pattern(validation_status=ValidationStatus.UNVALIDATED)
        result = validate_fragment(pattern)
        assert result.validation_status is ValidationStatus.VALID

    def test_does_not_mutate_input_pattern(self) -> None:
        pattern = build_pattern(validation_status=ValidationStatus.UNVALIDATED)
        validate_fragment(pattern)
        assert pattern.validation_status is ValidationStatus.UNVALIDATED

    def test_validate_fragment_is_deterministic(self) -> None:
        pattern = build_pattern(validation_status=ValidationStatus.UNVALIDATED)
        first = validate_fragment(pattern)
        second = validate_fragment(pattern)
        assert first.validation_status == second.validation_status
        assert first.model_dump(mode="json") == second.model_dump(mode="json")

    def test_multiple_rule_failures_all_reported(self) -> None:
        fragment = ScenarioGraph(nodes=[_policy_node("pol-1", ["iam:DeleteRole"])], edges=[])
        bad_finding = ExpectedFinding(
            id="f-bad",
            severity="high",
            family=FindingFamily.S3_PUBLIC_EXPOSURE,
            resource_ids=["missing-node"],
            expected_scanner_visibility="visible",
            ground_truth="bogus",
            remediation="n/a",
        )
        pattern = build_pattern().model_copy(
            update={"graph_fragment": fragment, "expected_findings": [bad_finding]}
        )

        reasons = validation_reasons(pattern)

        assert any("f-bad" in r for r in reasons)
        assert any("iam:DeleteRole" in r for r in reasons)
        assert len(reasons) >= 2


# --- integration: real normalizer/adapter output ---------------------------------


def _local_rule_catalog_source() -> SourceEntry:
    registry = load_registry(_REGISTRY)
    entry = registry.by_id("local-rule-catalog")
    assert entry is not None
    return entry


def _scenario_source() -> SourceEntry:
    # ``path`` is a provenance LABEL only (the adapter reads the dir passed as extract()'s
    # 2nd arg). Since path-traversal containment was added to ``SourceEntry.path``,
    # this uses the real registry's in-tree relative value (``out/``) rather than the
    # absolute fixture path.
    return SourceEntry(
        id="local-scenarios-out",
        name="cloudforge generated scenario dirs",
        type=SourceType.LOCAL_SCENARIO_DIR,
        path="out/",
        adapter="cloudforge_scenario",
        enabled=True,
        license="CC0-1.0",
        reuse_status=ReuseStatus.FULL_REUSE,
        allowed_for_training=True,
        notes="test",
    )


class TestRealNormalizedPatterns:
    def test_seed_rule_catalog_patterns_all_validate(self) -> None:
        adapter = RuleCatalogYamlAdapter()
        source = _local_rule_catalog_source()
        records = adapter.extract(source, Path("data/rule_catalog/seed_patterns.yaml"))
        normalizer = PatternNormalizer()

        results = [validate_fragment(normalizer.normalize(r)) for r in records]

        assert results
        invalid = [
            (r.id, validation_reasons(r))
            for r in [normalizer.normalize(r) for r in records]
            if validate_fragment(r).validation_status is not ValidationStatus.VALID
        ]
        assert all(r.validation_status is ValidationStatus.VALID for r in results), invalid

    def test_cloudforge_scenario_adapter_pattern_validates(self) -> None:
        adapter = CloudforgeScenarioAdapter()
        records = adapter.extract(_scenario_source(), _CI_CD_DIR)
        normalizer = PatternNormalizer()
        pattern = normalizer.normalize(records[0])

        result = validate_fragment(pattern)

        assert result.validation_status is ValidationStatus.VALID, validation_reasons(pattern)
