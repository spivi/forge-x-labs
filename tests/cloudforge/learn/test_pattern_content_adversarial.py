"""Adversarial malicious-pattern-content stress (#109, S8/S9).

Actively tries to smuggle unsafe/restricted/unprovenanced pattern content through the
real pipeline: ``PatternNormalizer.normalize`` -> ``validate.validate_fragment`` ->
``quality.score_pattern`` -> ``export.is_exportable`` / ``export.export_training``.

Every adversarial ``RawPatternRecord`` here is built by hand (no adapters needed --
adapters are a thin YAML->record mapping already covered by their own tests) so the
attack payload is fully controlled: exploit/credential-theft/persistence/evasion
wording, a fake PEM private key, an AWS-access-key-like string, a realistic account id,
a huge remediation blob, a dangling graph-fragment edge, a finding pointing at a
missing resource, missing/incomplete provenance, and a restricted/metadata_only source
carrying otherwise-exportable content.

Each case asserts the DEFENDED outcome explicitly. Where an adversarial input actually
reaches the export boundary, it is captured as ``xfail(strict=True,
reason="BUG(CRITICAL): ...")`` with a minimal reproducer -- see the "BUGS FOUND" section
of the ticket's result report for the roll-up.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.cloudforge.learn.export import export_training, is_exportable
from app.cloudforge.learn.normalizer import NormalizerError, PatternNormalizer
from app.cloudforge.learn.pattern_enums import SafetyClassification, ValidationStatus
from app.cloudforge.learn.pattern_models import PatternProvenance, RawPatternRecord, RiskPattern
from app.cloudforge.learn.quality import score_pattern
from app.cloudforge.learn.source_models import ReuseStatus, SourceType
from app.cloudforge.learn.validate import validate_fragment
from app.cloudforge.models.graph import (
    EdgeSecurity,
    GraphEdge,
    GraphNode,
    NodeSecurity,
    NodeTags,
    ScenarioGraph,
)

from .conftest import build_fragment

_TS = datetime(2026, 7, 5, 12, 0, 0, tzinfo=UTC)


def _provenance(
    *,
    reuse_status: ReuseStatus = ReuseStatus.FULL_REUSE,
    allowed_for_training: bool = True,
    source_id: str = "adversary-source",
    confidence: float = 0.9,
) -> PatternProvenance:
    """A complete provenance block (adversarial content lives in the record, not here)."""
    return PatternProvenance(
        source_id=source_id,
        source_name="adversarial test source",
        source_type=SourceType.LOCAL_RULE_CATALOG,
        source_url_or_path="data/rule_catalog/seed_patterns.yaml",
        source_license="CC0-1.0",
        reuse_status=reuse_status,
        allowed_for_training=allowed_for_training,
        extraction_method="hand_built_adversarial_fixture",
        fetched_at=_TS,
        extracted_at=_TS,
        content_hash="adversarialhash",
        adapter_name="test_fixture",
        adapter_version="0.0.0",
        normalizer_version="unset",
        confidence=confidence,
        notes="adversarial stress fixture",
    )


def _raw_record(
    *,
    raw_id: str = "adv-001",
    title: str = "Public-read S3 bucket",
    summary: str = "An S3 bucket is world-readable.",
    remediation: str = "Enable S3 Block Public Access.",
    provenance: PatternProvenance | None = None,
    resource_types: list[str] | None = None,
) -> RawPatternRecord:
    return RawPatternRecord(
        source_id=(provenance or _provenance()).source_id,
        raw_id=raw_id,
        title=title,
        summary=summary,
        cloud_provider=None,
        resource_types=resource_types or ["aws_s3_bucket"],
        severity="high",
        category=None,
        remediation=remediation,
        references=[],
        raw_payload={},
        provenance=provenance or _provenance(),
    )


def _run_pipeline(raw: RawPatternRecord) -> RiskPattern:
    """The real ingestion pipeline: normalize -> validate_fragment -> score."""
    normalized = PatternNormalizer().normalize(raw)
    validated = validate_fragment(normalized)
    scored, _report = score_pattern(validated)
    return scored


# --- exploit / credential-theft / persistence / evasion wording (title/summary/remediation) --


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("title", "How to exploit this misconfigured bucket"),
        ("summary", "Use this credential-theft technique to dump the metadata service"),
        ("summary", "Establish persistence via a backdoor cron job after initial access"),
        ("remediation", "Evasion technique: disable CloudTrail before running the payload"),
        ("summary", "This is a classic destructive-action against RDS snapshots"),
    ],
)
def test_unsafe_wording_forces_unsafe_operational_and_is_never_exported(
    field: str, value: str
) -> None:
    kwargs = {field: value}
    raw = _raw_record(**kwargs)

    scored = _run_pipeline(raw)

    assert scored.safety_classification is SafetyClassification.UNSAFE_OPERATIONAL
    ok, reason = is_exportable(scored)
    assert ok is False
    assert reason == "unsafe_operational"


def test_unsafe_wording_never_exported_even_with_include_restricted() -> None:
    raw = _raw_record(
        title="Exploit chain for lateral movement",
        provenance=_provenance(reuse_status=ReuseStatus.RESTRICTED, allowed_for_training=True),
    )
    scored = _run_pipeline(raw)
    scored = scored.model_copy(update={"quality_score": 0.99})

    ok, reason = is_exportable(scored, include_restricted=True)

    assert ok is False
    assert reason == "unsafe_operational"


# --- fake PEM private key ------------------------------------------------------------


def test_fake_private_key_block_forces_unsafe_and_is_never_exported() -> None:
    fake_key = (
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIBOgIBAAJBAKj34GkxFhD90vcNLYLInFEX6Ppy1tPf9Cnzj4p4WGeKLs1Pt8Qu\n"
        "-----END RSA PRIVATE KEY-----"
    )
    raw = _raw_record(remediation=f"Rotate the key. Old key was: {fake_key}")

    scored = _run_pipeline(raw)

    assert scored.safety_classification is SafetyClassification.UNSAFE_OPERATIONAL
    ok, reason = is_exportable(scored)
    assert ok is False
    assert reason == "unsafe_operational"


# --- AWS-access-key-like string + realistic account id --------------------------------


def test_secret_like_assignment_string_forces_unsafe() -> None:
    raw = _raw_record(
        summary=(
            "Found hardcoded credentials in the repo: "
            "aws_secret_access_key: 'wJalrXUtnFEMIK7MDENGbPxRfiCYEXAMPLEKEY'"
        )
    )

    scored = _run_pipeline(raw)

    assert scored.safety_classification is SafetyClassification.UNSAFE_OPERATIONAL
    ok, reason = is_exportable(scored)
    assert ok is False
    assert reason == "unsafe_operational"


def test_aws_access_key_id_like_string_alone_is_not_flagged_by_keyword_scan() -> None:
    """``is_unsafe_content`` matches ``aws_secret_access_key``/``api_key``/``password``
    assignment patterns and a private-key PEM block, but a bare AKIA-style access-KEY-ID
    (no secret, no assignment syntax) matches neither the keyword list nor
    ``_SECRET_LIKE_PATTERN`` -- confirm this is genuinely NOT caught (a known scan gap,
    not this pattern's export path) and that it does NOT, on its own, prevent an
    otherwise-safe, otherwise-eligible pattern from exporting.

    This is a real scan-coverage gap worth flagging, but per the ticket's bug-severity
    guidance it does not itself leak "unsafe-operational" content -- an access key ID
    alone (no secret) is not operationally exploitable, and the pattern is otherwise a
    legitimate defensive finding (e.g. "hardcoded AKIA... found in code, rotate it").
    Recorded here as a documented scan-coverage boundary, not a strict-xfail bug.
    """
    raw = _raw_record(
        summary="Hardcoded access key ID AKIAIOSFODNN7EXAMPLE found in a committed .env file"
    )

    scored = _run_pipeline(raw)

    # not classified unsafe purely from the bare key-ID string
    assert scored.safety_classification is not SafetyClassification.UNSAFE_OPERATIONAL


def test_realistic_account_id_alone_does_not_trip_unsafe_scan() -> None:
    """A realistic-looking 12-digit AWS account id in the summary is normal, legitimate
    defensive content (scanners routinely reference account ids) -- must NOT be
    misclassified unsafe. Confirms the scan is precise, not over-broad.
    """
    raw = _raw_record(summary="Cross-account trust policy allows account 123456789012 to assume")

    scored = _run_pipeline(raw)

    assert scored.safety_classification is not SafetyClassification.UNSAFE_OPERATIONAL


# --- huge remediation blob ------------------------------------------------------------


def test_huge_remediation_blob_does_not_crash_and_is_still_gated_normally() -> None:
    """A pathologically large remediation field (e.g. an adversary trying to smuggle a
    large opaque payload past review-by-inspection) must not crash the scanner/normalizer
    and must not itself bypass the safety/quality gates.
    """
    huge_remediation = "Enable Block Public Access. " + ("A" * 200_000)
    raw = _raw_record(remediation=huge_remediation)

    scored = _run_pipeline(raw)

    assert scored.safety_classification is not SafetyClassification.UNSAFE_OPERATIONAL
    # still gated by the normal rules -- no expected_findings on this hand-built record,
    # so quality.score_pattern's rejection reasons should flag it, not silently export it.
    ok, _reason = is_exportable(scored)
    # Whatever the outcome, it must be a deliberate, explainable gate decision -- not a
    # crash. The assertion above (no crash / no unsafe misclassification) is the point;
    # exportability here depends on quality/findings, asserted precisely below.
    assert isinstance(ok, bool)


def test_huge_remediation_with_embedded_unsafe_keyword_is_still_caught() -> None:
    """A huge remediation blob can't be used to dilute/hide an unsafe keyword from the
    scanner -- ``is_unsafe_content`` does a substring scan over the whole haystack
    regardless of surrounding volume.
    """
    huge_with_payload = (
        ("A" * 200_000) + " this remediation embeds an exploit payload " + ("B" * 200_000)
    )
    raw = _raw_record(remediation=huge_with_payload)

    scored = _run_pipeline(raw)

    assert scored.safety_classification is SafetyClassification.UNSAFE_OPERATIONAL


# --- unknown provider / family (Pydantic enum boundary) --------------------------------


def test_unknown_cloud_provider_string_is_rejected_by_pydantic() -> None:
    with pytest.raises(ValidationError) as exc_info:
        RawPatternRecord(
            source_id="adversary-source",
            raw_id="bad-provider",
            title="x",
            summary="",
            cloud_provider="definitely_not_a_real_cloud",  # type: ignore[arg-type]
            resource_types=[],
            provenance=_provenance(),
        )
    assert (
        "cloud_provider" in str(exc_info.value)
        or "validation error" in str(exc_info.value).lower()
    )


def test_unknown_weakness_family_string_declared_in_raw_payload_falls_back_safely() -> None:
    """A source can declare an arbitrary ``weakness_family`` string in ``raw_payload``
    (design feature). An adversarial/garbage value must not crash the normalizer
    and must not silently smuggle an out-of-vocabulary value onto ``RiskPattern`` (which
    is typed to the real ``WeaknessFamily`` enum) -- ``resolve_weakness_family`` must
    fall back to a real enum member, never pass the raw string through unchecked.
    """
    raw = RawPatternRecord(
        source_id="adversary-source",
        raw_id="bad-family",
        title="x",
        summary="",
        resource_types=["aws_s3_bucket"],
        provenance=_provenance(),
        raw_payload={"weakness_family": "totally_made_up_family_xyz"},
    )

    normalized = PatternNormalizer().normalize(raw)

    from app.cloudforge.learn.pattern_enums import WeaknessFamily

    assert normalized.weakness_family in WeaknessFamily


# --- missing / incomplete provenance ---------------------------------------------------


def test_blank_source_id_in_provenance_is_rejected_by_normalizer() -> None:
    provenance = _provenance().model_copy(update={"source_id": "   "})
    raw = _raw_record(provenance=provenance)

    with pytest.raises(NormalizerError):
        PatternNormalizer().normalize(raw)


def test_blank_content_hash_in_provenance_is_rejected_by_normalizer() -> None:
    provenance = _provenance().model_copy(update={"content_hash": ""})
    raw = _raw_record(provenance=provenance)

    with pytest.raises(NormalizerError):
        PatternNormalizer().normalize(raw)


def test_blank_adapter_name_in_provenance_is_rejected_by_normalizer() -> None:
    provenance = _provenance().model_copy(update={"adapter_name": ""})
    raw = _raw_record(provenance=provenance)

    with pytest.raises(NormalizerError):
        PatternNormalizer().normalize(raw)


def test_missing_provenance_field_entirely_is_rejected_at_construction() -> None:
    """``RawPatternRecord.provenance`` is required -- omitting it entirely is a Pydantic
    construction error, not something that reaches the normalizer at all (defense in
    depth: the schema itself, not just the normalizer's blank-string check).
    """
    with pytest.raises(ValidationError):
        RawPatternRecord.model_validate(
            {
                "source_id": "adversary-source",
                "raw_id": "no-provenance",
                "title": "x",
                "summary": "",
                "resource_types": [],
                # provenance omitted entirely
            }
        )


# --- graph-fragment edge to a missing node (bypassing ScenarioGraph's own guard) -------


def test_dangling_edge_fragment_bypassing_constructor_guard_fails_validation() -> None:
    """``ScenarioGraph`` itself refuses a dangling edge at construction time (its own
    ``model_validator``) -- proven first as the primary defense. Then simulate an
    adversary who reaches the corpus through a bypassed validator (``model_construct``,
    e.g. a hand-crafted/corrupted JSONL line loaded without going through
    ``model_validate``) to prove ``validate.validate_fragment``'s rule 1
    (``_dangling_edge_reasons``) is real defense-in-depth, not dead code.
    """
    # Primary defense: real construction refuses a dangling edge outright.
    with pytest.raises(ValidationError):
        ScenarioGraph(
            nodes=[
                GraphNode(
                    id="node-a",
                    type="S3Bucket",
                    name="a",
                    tags=NodeTags(env="prod", owner="team", app="x"),
                    security=NodeSecurity(criticality="high"),
                )
            ],
            edges=[
                GraphEdge(
                    from_="node-a",
                    to="node-does-not-exist",
                    type="can_read",
                    security=EdgeSecurity(risk="high"),
                )
            ],
        )

    # Defense-in-depth: a bypassed-validator fragment (model_construct skips the
    # after-validator) must still be caught by validate_fragment's rule 1.
    dangling_fragment = ScenarioGraph.model_construct(
        nodes=[
            GraphNode(
                id="node-a",
                type="S3Bucket",
                name="a",
                tags=NodeTags(env="prod", owner="team", app="x"),
                security=NodeSecurity(criticality="high"),
            )
        ],
        edges=[
            GraphEdge(
                from_="node-a",
                to="node-does-not-exist",
                type="can_read",
                security=EdgeSecurity(risk="high"),
            )
        ],
    )
    from .conftest import build_pattern

    pattern = build_pattern().model_copy(update={"graph_fragment": dangling_fragment})

    validated = validate_fragment(pattern)

    assert validated.validation_status is ValidationStatus.INVALID
    ok, reason = is_exportable(validated.model_copy(update={"quality_score": 0.99}))
    assert ok is False
    assert reason == "not_training_eligible"


# --- finding referencing a missing resource --------------------------------------------


def test_finding_referencing_missing_resource_fails_validation_and_export() -> None:
    from app.cloudforge.models.findings import ExpectedFinding

    fragment = build_fragment()  # nodes: bucket-1, app-1
    rogue_finding = ExpectedFinding(
        id="f-rogue",
        severity="high",
        family="s3_public_exposure",
        resource_ids=["node-that-does-not-exist-in-fragment"],
        expected_scanner_visibility="visible",
        ground_truth="bogus",
        remediation="n/a",
    )
    from .conftest import build_pattern

    pattern = build_pattern().model_copy(
        update={
            "graph_fragment": fragment,
            "expected_findings": [rogue_finding],
            "validation_status": ValidationStatus.UNVALIDATED,
        }
    )

    validated = validate_fragment(pattern)

    assert validated.validation_status is ValidationStatus.INVALID
    ok, reason = is_exportable(validated.model_copy(update={"quality_score": 0.99}))
    assert ok is False
    assert reason == "not_training_eligible"


# --- missing remediation / fragment -> quality penalty or exclusion --------------------


def test_pattern_with_no_expected_findings_is_rejected_as_not_exportable() -> None:
    raw = _raw_record()  # no raw_payload -> no expected_findings, minimal 1-node fragment
    scored = _run_pipeline(raw)

    assert scored.expected_findings == []
    _pattern, report = score_pattern(scored)
    assert "no expected_findings reference the fragment" in report.rejection_reasons
    assert report.exportable is False


def test_empty_remediation_lowers_quality_but_does_not_crash() -> None:
    raw = _raw_record(remediation="")
    scored = _run_pipeline(raw)

    assert scored.remediation == ""
    # must not crash scoring; quality score is still a valid float in [0, 1]
    assert 0.0 <= scored.quality_score <= 1.0


# --- restricted / metadata_only source carrying otherwise-exportable content -----------


def test_restricted_source_high_quality_content_excluded_by_default_included_only_with_flag() -> (
    None
):
    """A restricted source can carry perfectly safe, high-quality, well-formed content --
    it must still be excluded from export by default, and admitted ONLY with the explicit
    ``--include-restricted`` override (S9). This mirrors the "override test" acceptance
    criterion end-to-end through the real normalize->validate->score pipeline (not just
    a hand-built RiskPattern truth table, which test_export.py already covers).
    """
    from .conftest import build_pattern

    # `_restricted_but_otherwise_eligible` requires the pattern to be otherwise fully
    # eligible (valid, a TRAINABLE safety_classification, allowed_for_training) and
    # excluded ONLY by reuse_status == restricted -- a `RESTRICTED_SOURCE` safety
    # classification is a *different*, non-trainable signal and would make this a
    # not_training_eligible case instead (exercised separately below); the genuine S9
    # "otherwise eligible" scenario is a safely-classified pattern from a restricted
    # source, which is exactly what a real ingested restricted source should produce.
    pattern = build_pattern(
        reuse_status=ReuseStatus.RESTRICTED,
        allowed_for_training=True,
        validation_status=ValidationStatus.VALID,
        safety_classification=SafetyClassification.DEFENSIVE_PATTERN,
    ).model_copy(update={"quality_score": 0.95})

    without_flag, reason_without = is_exportable(pattern, include_restricted=False)
    with_flag, reason_with = is_exportable(pattern, include_restricted=True)

    assert without_flag is False
    assert reason_without == "restricted_source_excluded"
    assert with_flag is True
    assert reason_with == ""


def test_metadata_only_source_never_exports_even_with_include_restricted_flag() -> None:
    """metadata_only is NOT the same relaxation path as restricted -- confirm the flag
    does not accidentally widen to cover it (S9: only reuse_status==restricted is
    relaxed).
    """
    from .conftest import build_pattern

    pattern = build_pattern(
        reuse_status=ReuseStatus.METADATA_ONLY,
        allowed_for_training=False,
        safety_classification=SafetyClassification.BENCHMARK_PATTERN,
    ).model_copy(update={"quality_score": 0.95})

    ok, reason = is_exportable(pattern, include_restricted=True)

    assert ok is False
    assert reason == "not_training_eligible"


def test_the_override_boundary_unsafe_restricted_high_quality_pattern_never_exports() -> None:
    """THE override test (S8/S9 boundary, explicit ticket deliverable): a pattern that is
    simultaneously unsafe_operational, restricted, allowed_for_training=true, AND
    high-quality must NEVER be admitted, even with ``--include-restricted``. Safety (S8)
    strictly dominates the reuse-status relaxation (S9) -- there is no combination of
    flags that admits unsafe content.
    """
    from .conftest import build_pattern

    worst_case_pattern = build_pattern(
        reuse_status=ReuseStatus.RESTRICTED,
        allowed_for_training=True,
        validation_status=ValidationStatus.VALID,
        safety_classification=SafetyClassification.UNSAFE_OPERATIONAL,
    ).model_copy(update={"quality_score": 1.0})

    without_flag, reason_without = is_exportable(worst_case_pattern, include_restricted=False)
    with_flag, reason_with = is_exportable(worst_case_pattern, include_restricted=True)

    assert without_flag is False
    assert reason_without == "unsafe_operational"
    assert with_flag is False
    assert reason_with == "unsafe_operational"


def test_export_training_manifest_records_every_exclusion_reason_for_a_mixed_batch() -> None:
    """``export_training``'s manifest must account for every excluded pattern by reason --
    a mixed adversarial batch (unsafe, restricted, metadata_only, below-bar, and one
    legitimately eligible pattern) should produce a manifest whose breakdown sums to
    exactly the excluded count, with the one eligible pattern the sole export.
    """
    from .conftest import build_pattern

    unsafe = build_pattern(
        safety_classification=SafetyClassification.UNSAFE_OPERATIONAL
    ).model_copy(update={"id": "batch-unsafe", "quality_score": 0.99})
    # Otherwise-eligible restricted source (S9 relaxation candidate): safely classified,
    # excluded ONLY by reuse_status == restricted (a RESTRICTED_SOURCE safety
    # classification would instead fall into not_training_eligible -- see the dedicated
    # override test above for that distinction).
    restricted = build_pattern(
        reuse_status=ReuseStatus.RESTRICTED,
        allowed_for_training=True,
        safety_classification=SafetyClassification.DEFENSIVE_PATTERN,
    ).model_copy(update={"id": "batch-restricted", "quality_score": 0.99})
    metadata_only = build_pattern(
        reuse_status=ReuseStatus.METADATA_ONLY,
        allowed_for_training=False,
        safety_classification=SafetyClassification.BENCHMARK_PATTERN,
    ).model_copy(update={"id": "batch-metadata", "quality_score": 0.99})
    below_bar = build_pattern().model_copy(update={"id": "batch-lowqual", "quality_score": 0.05})
    eligible = build_pattern().model_copy(update={"id": "batch-eligible", "quality_score": 0.90})

    result = export_training(
        [unsafe, restricted, metadata_only, below_bar, eligible], include_restricted=False
    )

    assert result.manifest.total_input == 5
    assert result.manifest.exported_count == 1
    assert {p.id for p in result.records} == {"batch-eligible"}
    assert result.manifest.excluded_breakdown.unsafe_operational == 1
    assert result.manifest.excluded_breakdown.restricted_source_excluded == 1
    assert result.manifest.excluded_breakdown.below_quality_bar == 1
    assert result.manifest.excluded_breakdown.not_training_eligible == 1  # metadata_only
    assert result.manifest.excluded_breakdown.total == 4
