"""Hand-authored seed ``graph_fragment`` tests (ticket #98).

The 14 seed patterns in ``data/rule_catalog/seed_patterns.yaml`` each embed a
hand-authored, semantically-correct ``graph_fragment`` + ``expected_findings``.
These tests prove, against the REAL catalog through the REAL adapter/normalizer:

- every seed's fragment flows through ``raw_payload["graph"]`` and is reused
  VERBATIM by the normalizer (never the minimal edge-less fallback);
- every fragment passes ``validate_fragment`` (endpoints resolve, known types,
  findings reference real nodes, no forbidden destructive actions);
- edges carry REAL cloud semantics — the exact false shapes the #96 review
  rejected (a policy as an actor, fabricated DataSet nodes, kms silently mapped
  to Application) are asserted ABSENT;
- the corpus quality outcome is HONEST: the two absence-of-logging seeds are
  inherently simple (no real edge exists) and legitimately score below the 0.70
  export bar — they are warned, not gamed.

No internet, no ML — pure YAML + adapter + normalizer + validator + scorer.
"""

from __future__ import annotations

import fnmatch
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.cloudforge import constants
from app.cloudforge.learn.adapters.rule_catalog_yaml import RuleCatalogYamlAdapter
from app.cloudforge.learn.normalizer import PatternNormalizer
from app.cloudforge.learn.pattern_enums import ValidationStatus
from app.cloudforge.learn.pattern_models import RiskPattern
from app.cloudforge.learn.quality import EXPORT_QUALITY_BAR, score_pattern
from app.cloudforge.learn.registry import get_entry, load_registry
from app.cloudforge.learn.validate import validate_fragment, validation_reasons
from app.cloudforge.models.findings import FindingFamily
from app.cloudforge.models.graph import EdgeType, NodeType, ScenarioGraph

_REGISTRY = Path("data/source_registry.yaml")
_SOURCE_ID = "local-rule-catalog"
_SEED_COUNT = 14

# The two inherently-simple absence-of-logging seeds: their risk IS a missing
# edge, so their fragments honestly have no edges and score below the export bar.
_HONESTLY_SIMPLE_SEEDS = {
    "s3-missing-access-logging-aws-001",
    "cloudtrail-logging-missing-aws-008",
}

# Seeds where a DataSet sink is inherent to the risk (exposed objects/secrets).
_DATA_SINK_SEEDS = {
    "s3-public-read-no-compensating-control-aws-002",
    "iam-broad-s3-read-sensitive-bucket-aws-003",
    "iam-passrole-chain-sensitive-runtime-aws-004",
    "storage-account-public-blob-access-azure-009",
    "key-vault-public-network-access-azure-010",
    "storage-bucket-public-iam-member-gcp-011",
    "secret-manager-secret-overly-broad-iam-access-gcp-014",
}

# Closest-real-FindingFamily per seed (non-obvious mappings documented in the YAML).
_EXPECTED_FINDING_FAMILIES: dict[str, set[FindingFamily]] = {
    "s3-missing-access-logging-aws-001": {FindingFamily.S3_LOGGING_MISSING},
    "s3-public-read-no-compensating-control-aws-002": {FindingFamily.S3_PUBLIC_EXPOSURE},
    "iam-broad-s3-read-sensitive-bucket-aws-003": {FindingFamily.IAM_EXCESSIVE_PRIVILEGE},
    "iam-passrole-chain-sensitive-runtime-aws-004": {
        FindingFamily.IAM_PASSROLE_RISK,
        FindingFamily.IAM_EXCESSIVE_PRIVILEGE,
    },
    "security-group-ssh-open-to-internet-aws-005": {FindingFamily.SECURITY_GROUP_OVEREXPOSED},
    "security-group-admin-ui-open-to-internet-aws-006": {FindingFamily.SECURITY_GROUP_OVEREXPOSED},
    "kms-key-policy-wildcard-principal-aws-007": {FindingFamily.IAM_EXCESSIVE_PRIVILEGE},
    "cloudtrail-logging-missing-aws-008": {FindingFamily.S3_LOGGING_MISSING},
    "storage-account-public-blob-access-azure-009": {FindingFamily.S3_PUBLIC_EXPOSURE},
    "key-vault-public-network-access-azure-010": {FindingFamily.SECURITY_GROUP_OVEREXPOSED},
    "storage-bucket-public-iam-member-gcp-011": {FindingFamily.S3_PUBLIC_EXPOSURE},
    "service-account-overprivileged-project-role-gcp-012": {FindingFamily.IAM_EXCESSIVE_PRIVILEGE},
    "cicd-pipeline-long-lived-static-cloud-creds-aws-013": {FindingFamily.IAM_EXCESSIVE_PRIVILEGE},
    "secret-manager-secret-overly-broad-iam-access-gcp-014": {
        FindingFamily.IAM_EXCESSIVE_PRIVILEGE
    },
}


@pytest.fixture(scope="module")
def seeds_by_raw_id() -> dict[str, RiskPattern]:
    """The real 14-seed catalog, normalized once per module, keyed by raw seed id."""
    registry = load_registry(_REGISTRY)
    entry = get_entry(registry, _SOURCE_ID)
    assert entry.path is not None
    records = RuleCatalogYamlAdapter().extract(entry, Path(entry.path))
    normalizer = PatternNormalizer()
    return {record.raw_id: normalizer.normalize(record) for record in records}


def _edge_keys(pattern: RiskPattern) -> set[str]:
    return {edge.key for edge in pattern.graph_fragment.edges}


def _node_types(pattern: RiskPattern) -> dict[str, NodeType]:
    return {node.id: node.type for node in pattern.graph_fragment.nodes}


# --- the fragments flow through raw_payload["graph"] and are reused verbatim ---------


class TestEmbeddedFragmentFlow:
    def test_all_14_seeds_embed_a_parseable_graph_in_raw_payload(self) -> None:
        registry = load_registry(_REGISTRY)
        entry = get_entry(registry, _SOURCE_ID)
        assert entry.path is not None
        records = RuleCatalogYamlAdapter().extract(entry, Path(entry.path))

        assert len(records) == _SEED_COUNT
        for record in records:
            graph_json = record.raw_payload.get("graph")
            assert isinstance(graph_json, str) and graph_json, record.raw_id
            fragment = ScenarioGraph.model_validate_json(graph_json)
            assert fragment.nodes, record.raw_id

    def test_normalizer_reuses_the_authored_fragment_not_the_minimal_fallback(
        self, seeds_by_raw_id: dict[str, RiskPattern]
    ) -> None:
        registry = load_registry(_REGISTRY)
        entry = get_entry(registry, _SOURCE_ID)
        assert entry.path is not None
        records = RuleCatalogYamlAdapter().extract(entry, Path(entry.path))

        for record in records:
            graph_json = record.raw_payload["graph"]
            assert isinstance(graph_json, str)
            authored = ScenarioGraph.model_validate_json(graph_json)
            normalized = seeds_by_raw_id[record.raw_id].graph_fragment

            assert normalized == authored, record.raw_id
            # The minimal fallback names nodes "resource-<n>" — none may survive.
            assert not any(n.id.startswith("resource-") for n in normalized.nodes)

    def test_every_seed_has_at_least_one_expected_finding(
        self, seeds_by_raw_id: dict[str, RiskPattern]
    ) -> None:
        assert len(seeds_by_raw_id) == _SEED_COUNT
        for raw_id, pattern in seeds_by_raw_id.items():
            assert pattern.expected_findings, raw_id

    def test_normalizing_the_seed_catalog_twice_is_byte_identical(self) -> None:
        # Extraction timestamps are wall-clock, so both runs pin the same stamp —
        # everything else (fragments, findings, scores' inputs) must be identical.
        registry = load_registry(_REGISTRY)
        entry = get_entry(registry, _SOURCE_ID)
        assert entry.path is not None
        stamp = datetime(2026, 7, 5, 12, 0, 0, tzinfo=UTC)

        def _normalize_all() -> dict[str, dict[str, object]]:
            records = RuleCatalogYamlAdapter().extract(
                entry, Path(entry.path or ""), extracted_at=stamp
            )
            normalizer = PatternNormalizer()
            return {r.raw_id: normalizer.normalize(r).model_dump(mode="json") for r in records}

        assert _normalize_all() == _normalize_all()


# --- every fragment passes validate_fragment ------------------------------------------


class TestFragmentValidation:
    def test_all_14_fragments_validate_as_valid(
        self, seeds_by_raw_id: dict[str, RiskPattern]
    ) -> None:
        for raw_id, pattern in seeds_by_raw_id.items():
            validated = validate_fragment(pattern)
            assert validated.validation_status is ValidationStatus.VALID, (
                raw_id,
                validation_reasons(pattern),
            )

    def test_every_finding_references_only_real_fragment_nodes(
        self, seeds_by_raw_id: dict[str, RiskPattern]
    ) -> None:
        for raw_id, pattern in seeds_by_raw_id.items():
            node_ids = {node.id for node in pattern.graph_fragment.nodes}
            for finding in pattern.expected_findings:
                assert finding.resource_ids, (raw_id, finding.id)
                assert set(finding.resource_ids) <= node_ids, (raw_id, finding.id)

    def test_no_node_grants_a_forbidden_destructive_action(
        self, seeds_by_raw_id: dict[str, RiskPattern]
    ) -> None:
        for raw_id, pattern in seeds_by_raw_id.items():
            for node in pattern.graph_fragment.nodes:
                raw_actions = node.attributes.get("actions", [])
                actions = raw_actions if isinstance(raw_actions, list) else [raw_actions]
                for action in actions:
                    matched = [
                        forbidden
                        for forbidden in constants.FORBIDDEN_PERMISSION_PATTERNS
                        if fnmatch.fnmatch(action, forbidden)
                    ]
                    assert not matched, (raw_id, node.id, action)

    def test_finding_families_match_each_seed_weakness(
        self, seeds_by_raw_id: dict[str, RiskPattern]
    ) -> None:
        for raw_id, pattern in seeds_by_raw_id.items():
            families = {finding.family for finding in pattern.expected_findings}
            assert families == _EXPECTED_FINDING_FAMILIES[raw_id], raw_id


# --- the edges are semantically REAL (the #96 false shapes are absent) ----------------


class TestFragmentSemantics:
    def test_passrole_seed_models_the_real_escalation_chain(
        self, seeds_by_raw_id: dict[str, RiskPattern]
    ) -> None:
        keys = _edge_keys(seeds_by_raw_id["iam-passrole-chain-sensitive-runtime-aws-004"])
        assert "cicd-identity->assumes->role-deploy" in keys
        assert "role-deploy->can_pass_role->role-runtime" in keys
        assert "role-runtime->can_read->s3-customer-exports" in keys
        assert "s3-customer-exports->stores_sensitive_data->data-customer-exports" in keys

    def test_no_policy_node_is_ever_an_edge_actor(
        self, seeds_by_raw_id: dict[str, RiskPattern]
    ) -> None:
        # The #96 fabrication emitted `IAMPolicy -can_read-> IAMRole`. A policy is a
        # document ATTACHED to an identity, never an actor: across all 14 fragments no
        # edge may originate from an IAMPolicy node.
        for raw_id, pattern in seeds_by_raw_id.items():
            types = _node_types(pattern)
            for edge in pattern.graph_fragment.edges:
                assert types[edge.from_] is not NodeType.IAM_POLICY, (raw_id, edge.key)

    def test_attached_policy_edges_attach_an_identity_or_resource_to_a_policy(
        self, seeds_by_raw_id: dict[str, RiskPattern]
    ) -> None:
        for raw_id, pattern in seeds_by_raw_id.items():
            types = _node_types(pattern)
            for edge in pattern.graph_fragment.edges:
                if edge.type is EdgeType.ATTACHED_POLICY:
                    assert types[edge.to] is NodeType.IAM_POLICY, (raw_id, edge.key)

    def test_can_pass_role_edges_connect_two_iam_roles(
        self, seeds_by_raw_id: dict[str, RiskPattern]
    ) -> None:
        for raw_id, pattern in seeds_by_raw_id.items():
            types = _node_types(pattern)
            for edge in pattern.graph_fragment.edges:
                if edge.type is EdgeType.CAN_PASS_ROLE:
                    assert types[edge.from_] is NodeType.IAM_ROLE, (raw_id, edge.key)
                    assert types[edge.to] is NodeType.IAM_ROLE, (raw_id, edge.key)

    def test_stores_sensitive_data_edges_end_in_a_dataset(
        self, seeds_by_raw_id: dict[str, RiskPattern]
    ) -> None:
        for raw_id, pattern in seeds_by_raw_id.items():
            types = _node_types(pattern)
            for edge in pattern.graph_fragment.edges:
                if edge.type is EdgeType.STORES_SENSITIVE_DATA:
                    assert types[edge.to] is NodeType.DATASET, (raw_id, edge.key)
                    assert types[edge.from_] in {NodeType.S3_BUCKET, NodeType.APPLICATION}, (
                        raw_id,
                        edge.key,
                    )

    def test_kms_seed_models_the_key_via_its_key_policy_not_application(
        self, seeds_by_raw_id: dict[str, RiskPattern]
    ) -> None:
        # #96 silently mapped aws_kms_key -> Application; #98 models the key via its
        # KEY POLICY (IAMPolicy, documented) with the wildcard-"*" trust as the actor.
        pattern = seeds_by_raw_id["kms-key-policy-wildcard-principal-aws-007"]
        types = _node_types(pattern)
        assert NodeType.APPLICATION not in types.values()
        assert types["pol-cmk-key-policy"] is NodeType.IAM_POLICY
        assert "acct-any-principal->can_read->pol-cmk-key-policy" in _edge_keys(pattern)

    def test_public_read_seed_models_direct_internet_exposure_of_stored_data(
        self, seeds_by_raw_id: dict[str, RiskPattern]
    ) -> None:
        keys = _edge_keys(seeds_by_raw_id["s3-public-read-no-compensating-control-aws-002"])
        assert "acct-main->exposed_to_internet->s3-public-bucket" in keys
        assert "s3-public-bucket->stores_sensitive_data->data-bucket-objects" in keys

    def test_azure_storage_account_and_container_are_distinct_nodes(
        self, seeds_by_raw_id: dict[str, RiskPattern]
    ) -> None:
        pattern = seeds_by_raw_id["storage-account-public-blob-access-azure-009"]
        types = _node_types(pattern)
        assert types["stacct-appdata"] is NodeType.S3_BUCKET
        assert types["container-public-assets"] is NodeType.S3_BUCKET
        assert "stacct-appdata->exposed_to_internet->container-public-assets" in _edge_keys(
            pattern
        )

    def test_ssh_seed_exposes_the_subnet_through_the_open_security_group(
        self, seeds_by_raw_id: dict[str, RiskPattern]
    ) -> None:
        pattern = seeds_by_raw_id["security-group-ssh-open-to-internet-aws-005"]
        assert "sg-ssh-open->exposed_to_internet->subnet-app-a" in _edge_keys(pattern)
        sg_node = next(n for n in pattern.graph_fragment.nodes if n.id == "sg-ssh-open")
        assert sg_node.attributes["ingress_cidr"] == "0.0.0.0/0"
        assert sg_node.attributes["ingress_port"] == "22"

    def test_logging_absence_seeds_model_the_absence_with_no_fabricated_edges(
        self, seeds_by_raw_id: dict[str, RiskPattern]
    ) -> None:
        # The risk IS a missing logs_to edge; fabricating any edge would be false.
        bucket_seed = seeds_by_raw_id["s3-missing-access-logging-aws-001"]
        assert bucket_seed.graph_fragment.edges == []
        assert set(_node_types(bucket_seed).values()) == {NodeType.S3_BUCKET, NodeType.LOG_TRAIL}

        trail_seed = seeds_by_raw_id["cloudtrail-logging-missing-aws-008"]
        assert trail_seed.graph_fragment.edges == []
        assert set(_node_types(trail_seed).values()) == {NodeType.ACCOUNT, NodeType.LOG_TRAIL}

    def test_dataset_nodes_appear_only_where_data_exposure_is_inherent(
        self, seeds_by_raw_id: dict[str, RiskPattern]
    ) -> None:
        # The #96 review rejected DataSet nodes forced into scenarios that never
        # declared data; a DataSet sink may exist only where the risk IS about data.
        for raw_id, pattern in seeds_by_raw_id.items():
            has_dataset = NodeType.DATASET in _node_types(pattern).values()
            assert has_dataset == (raw_id in _DATA_SINK_SEEDS), raw_id


# --- honest exportability outcome ------------------------------------------------------


class TestHonestExportability:
    def test_pipeline_yields_the_honest_exportable_count(
        self, seeds_by_raw_id: dict[str, RiskPattern]
    ) -> None:
        # 14/14 validate; 12/14 clear the 0.70 export bar. The two
        # absence-of-logging seeds honestly stay below it (edge-less fragments are
        # structurally poor by design, because the risk is a MISSING edge) — they
        # carry warnings, not rejection reasons, and are NOT gamed above the bar.
        exportable_ids: set[str] = set()
        below_bar_ids: set[str] = set()
        for raw_id, pattern in seeds_by_raw_id.items():
            validated = validate_fragment(pattern)
            assert validated.validation_status is ValidationStatus.VALID, raw_id
            scored, report = score_pattern(validated)
            assert report.rejection_reasons == [], (raw_id, report.rejection_reasons)
            if report.exportable:
                exportable_ids.add(raw_id)
            else:
                below_bar_ids.add(raw_id)
                assert scored.quality_score < EXPORT_QUALITY_BAR
                assert "graph_fragment has no edges" in report.warnings

        assert len(exportable_ids) == 12
        assert below_bar_ids == _HONESTLY_SIMPLE_SEEDS

    def test_validated_seeds_are_training_eligible(
        self, seeds_by_raw_id: dict[str, RiskPattern]
    ) -> None:
        for raw_id, pattern in seeds_by_raw_id.items():
            validated = validate_fragment(pattern)
            assert validated.training_eligible is True, raw_id
