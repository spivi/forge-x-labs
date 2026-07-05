"""Shared fixtures for the learning-corpus tests.

``sample_provenance`` / ``sample_fragment`` build the minimal-but-real pieces a
``RiskPattern`` needs so tests exercise the actual ``ScenarioGraph`` /
``PatternProvenance`` models rather than mocks.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from app.cloudforge.learn.pattern_models import (
    CloudProvider,
    Domain,
    PatternProvenance,
    RiskPattern,
    SafetyClassification,
    ValidationStatus,
    WeaknessFamily,
)
from app.cloudforge.learn.source_models import ReuseStatus, SourceType
from app.cloudforge.models.findings import ExpectedFinding, FindingFamily
from app.cloudforge.models.graph import ScenarioGraph

_TS = datetime(2026, 7, 5, 12, 0, 0)


def build_provenance(
    *,
    reuse_status: ReuseStatus = ReuseStatus.FULL_REUSE,
    allowed_for_training: bool = True,
) -> PatternProvenance:
    """A complete provenance with tunable reuse posture (for the truth-table tests)."""
    return PatternProvenance(
        source_id="local-rule-catalog",
        source_name="cloudforge local curated rule catalog",
        source_type=SourceType.LOCAL_RULE_CATALOG,
        source_url_or_path="data/rule_catalog/seed_patterns.yaml",
        source_license="CC0-1.0",
        reuse_status=reuse_status,
        allowed_for_training=allowed_for_training,
        extraction_method="yaml_catalog",
        fetched_at=_TS,
        extracted_at=_TS,
        content_hash="deadbeef",
        adapter_name="rule_catalog_yaml",
        adapter_version="0.1.0",
        normalizer_version="0.1.0",
        confidence=0.75,
        notes="seed pattern",
    )


def build_fragment() -> ScenarioGraph:
    """A minimal two-node/one-edge fragment using the real graph model."""
    return ScenarioGraph.model_validate(
        {
            "nodes": [
                {
                    "id": "bucket-1",
                    "type": "S3Bucket",
                    "name": "public-data",
                    "tags": {"env": "prod", "owner": "team", "app": "analytics"},
                    "security": {"criticality": "high"},
                    "attributes": {"acl": "public-read"},
                },
                {
                    "id": "app-1",
                    "type": "Application",
                    "name": "exporter",
                    "tags": {"env": "prod", "owner": "team", "app": "analytics"},
                    "security": {"criticality": "medium"},
                },
            ],
            "edges": [
                {
                    "from": "app-1",
                    "to": "bucket-1",
                    "type": "can_read",
                    "security": {"risk": "high"},
                }
            ],
        }
    )


def build_finding() -> ExpectedFinding:
    """One expected finding referencing the fragment's bucket node."""
    return ExpectedFinding(
        id="f-1",
        severity="high",
        family=FindingFamily.S3_PUBLIC_EXPOSURE,
        resource_ids=["bucket-1"],
        expected_scanner_visibility="visible",
        ground_truth="bucket is public-read",
        remediation="set the ACL to private",
    )


def build_pattern(
    *,
    reuse_status: ReuseStatus = ReuseStatus.FULL_REUSE,
    allowed_for_training: bool = True,
    validation_status: ValidationStatus = ValidationStatus.VALID,
    safety_classification: SafetyClassification = SafetyClassification.DEFENSIVE_PATTERN,
) -> RiskPattern:
    """A complete, valid ``RiskPattern`` with tunable eligibility inputs."""
    return RiskPattern(
        id="s3-public-read-aws-001",
        title="Public-read S3 bucket",
        summary="An S3 bucket is world-readable via a public-read ACL.",
        cloud_provider=CloudProvider.AWS,
        domains=[Domain.STORAGE, Domain.DATA],
        weakness_family=WeaknessFamily.S3_PUBLIC_EXPOSURE,
        severity="high",
        affected_resource_types=["aws_s3_bucket"],
        risky_relationships=["can_read"],
        missing_controls=["block_public_access"],
        negative_controls=["public_read_acl"],
        compensating_controls=[],
        graph_fragment=build_fragment(),
        expected_findings=[build_finding()],
        remediation="Enable S3 Block Public Access.",
        detection_hints=["acl == public-read"],
        control_mappings=["CCM:DSP-01"],
        source_mappings=["CKV_AWS_20"],
        provenance=build_provenance(
            reuse_status=reuse_status, allowed_for_training=allowed_for_training
        ),
        confidence=0.75,
        realism_score=0.8,
        quality_score=0.85,
        validation_status=validation_status,
        safety_classification=safety_classification,
    )


@pytest.fixture
def sample_provenance() -> PatternProvenance:
    return build_provenance()


@pytest.fixture
def sample_pattern() -> RiskPattern:
    return build_pattern()
