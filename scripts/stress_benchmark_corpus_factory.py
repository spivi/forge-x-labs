"""Synthesizes ``RiskPattern`` corpora at scale for the FXL-112 benchmark.

Builds patterns programmatically from the two shipped seed-pattern shapes (mirroring
``tests/cloudforge/learn/conftest.py::build_pattern``) x a deterministic variation
axis (cloud provider, weakness family, node/edge suffix), so a 100,000-pattern corpus
is generated in-memory without ever touching a real adapter/fetch source. This is
pure test data, not a new learn-pipeline capability.
"""

from __future__ import annotations

from datetime import datetime

from app.cloudforge.learn.pattern_enums import (
    CloudProvider,
    Domain,
    SafetyClassification,
    ValidationStatus,
    WeaknessFamily,
)
from app.cloudforge.learn.pattern_models import PatternProvenance, RiskPattern
from app.cloudforge.learn.source_models import ReuseStatus, SourceType
from app.cloudforge.models.findings import ExpectedFinding, FindingFamily
from app.cloudforge.models.graph import ScenarioGraph

_TS = datetime(2026, 7, 5, 12, 0, 0)
_PROVIDERS = list(CloudProvider)
_FAMILIES = list(WeaknessFamily)


def _provenance(index: int) -> PatternProvenance:
    return PatternProvenance(
        source_id=f"synthetic-source-{index % 7}",
        source_name="synthetic benchmark corpus",
        source_type=SourceType.LOCAL_RULE_CATALOG,
        source_url_or_path="scripts/stress_benchmark_corpus_factory.py",
        source_license="CC0-1.0",
        reuse_status=ReuseStatus.FULL_REUSE,
        allowed_for_training=True,
        extraction_method="synthetic",
        fetched_at=_TS,
        extracted_at=_TS,
        content_hash=f"hash-{index:08d}",
        adapter_name="synthetic",
        adapter_version="0.1.0",
        normalizer_version="0.1.0",
        confidence=0.5 + (index % 5) / 10,
        notes="benchmark-generated",
    )


def _fragment(index: int) -> ScenarioGraph:
    bucket_id = f"bucket-{index}"
    app_id = f"app-{index}"
    return ScenarioGraph.model_validate(
        {
            "nodes": [
                {
                    "id": bucket_id,
                    "type": "S3Bucket",
                    "name": f"data-{index}",
                    "tags": {"env": "prod", "owner": "team", "app": "bench"},
                    "security": {"criticality": "high"},
                    "attributes": {"acl": "public-read"},
                },
                {
                    "id": app_id,
                    "type": "Application",
                    "name": f"exporter-{index}",
                    "tags": {"env": "prod", "owner": "team", "app": "bench"},
                    "security": {"criticality": "medium"},
                },
            ],
            "edges": [
                {"from": app_id, "to": bucket_id, "type": "can_read", "security": {"risk": "high"}}
            ],
        }
    )


def _finding(index: int) -> ExpectedFinding:
    return ExpectedFinding(
        id=f"f-{index}",
        severity="high",
        family=FindingFamily.S3_PUBLIC_EXPOSURE,
        resource_ids=[f"bucket-{index}"],
        expected_scanner_visibility="visible",
        ground_truth="synthetic benchmark finding",
        remediation="set the ACL to private",
    )


def build_pattern(index: int) -> RiskPattern:
    """Build one deterministic, varied ``RiskPattern`` for benchmark index ``index``.

    The dedup key fields (``cloud_provider``, ``weakness_family``,
    ``affected_resource_types``, ``risky_relationships``, ``missing_controls``,
    ``compensating_controls``) all vary with ``index`` (not just provider/family, a
    96-value space that would collide constantly past ~100 patterns) so the corpus
    stays near-unique at scale; :func:`build_corpus` then injects the only
    *intentional* duplicates on top of this.
    """
    provider = _PROVIDERS[index % len(_PROVIDERS)]
    family = _FAMILIES[index % len(_FAMILIES)]
    resource_bucket = index % 977  # large prime spreads the dedup-key resource axis
    return RiskPattern(
        id=f"bench-pattern-{index:08d}",
        title=f"Synthetic pattern {index}",
        summary="Benchmark-only synthetic pattern for scale measurement.",
        cloud_provider=provider,
        domains=[Domain.STORAGE, Domain.DATA],
        weakness_family=family,
        severity="high",
        affected_resource_types=[f"aws_s3_bucket_{resource_bucket}"],
        risky_relationships=["can_read"],
        missing_controls=["block_public_access"],
        negative_controls=["public_read_acl"],
        compensating_controls=[],
        graph_fragment=_fragment(index),
        expected_findings=[_finding(index)],
        remediation="Enable S3 Block Public Access.",
        detection_hints=["acl == public-read"],
        control_mappings=["CCM:DSP-01"],
        source_mappings=[f"CKV_SYN_{index % 100}"],
        provenance=_provenance(index),
        confidence=0.75,
        realism_score=0.8,
        quality_score=0.0,
        validation_status=ValidationStatus.VALID,
        safety_classification=SafetyClassification.DEFENSIVE_PATTERN,
    )


def build_corpus(n: int) -> list[RiskPattern]:
    """Build ``n`` synthetic patterns. A small fraction share a dedup key on purpose
    (every 11th index reuses index 0's key-relevant fields) so ``dedup()`` has real
    duplicate groups to fold at scale, not just N singleton groups.
    """
    patterns = [build_pattern(i) for i in range(n)]
    for i in range(0, n, 11):
        if i == 0:
            continue
        dup_source = patterns[0]
        patterns[i] = patterns[i].model_copy(
            update={
                "id": f"bench-pattern-dup-{i:08d}",
                "cloud_provider": dup_source.cloud_provider,
                "weakness_family": dup_source.weakness_family,
                "affected_resource_types": dup_source.affected_resource_types,
                "risky_relationships": dup_source.risky_relationships,
                "missing_controls": dup_source.missing_controls,
                "compensating_controls": dup_source.compensating_controls,
            }
        )
    return patterns
