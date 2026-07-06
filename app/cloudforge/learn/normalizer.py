"""``PatternNormalizer``: ``RawPatternRecord`` -> ``RiskPattern`` (design §9.1).

Maps adapter fields onto the ontology (design §6), sorts every list field for
determinism, reuses/builds the ``graph_fragment`` as a real ``ScenarioGraph``, assigns
``safety_classification`` from ``reuse_status`` plus a keyword/secret content scan,
stamps provenance completely (raising on incomplete provenance), and pins
``normalizer_version``. ``validation_status`` starts ``unvalidated`` (ticket #67's
validator promotes it); ``training_eligible`` is a ``computed_field`` on ``RiskPattern``.

FXL-96: a source (e.g. the ``rule_catalog_yaml`` seed catalog) declares structured
``missing_controls``/``compensating_controls``/``negative_controls``/
``risky_relationships``/``weakness_family`` inside ``raw_payload``; those are preserved
onto the ``RiskPattern`` (sorted, deterministic) instead of dropped, and a seed's own
declared ``weakness_family`` is honored rather than over-generalized (resolving the #93
dedup collision). The normalizer does NOT invent a graph from flat fields — a seed
declares a risk *pattern*, not a graph — so the fragment is either a real graph embedded
in ``raw_payload`` (the ``cloudforge_scenario`` path) or an honest minimal fragment (one
generic node per declared resource type, no fabricated edges); ``expected_findings``
stays empty. Hand-authored per-seed fragments/findings are a separate ticket (#98).

No ML, no embeddings — pure deterministic field mapping (guiding directive, design §1).
"""

from __future__ import annotations

import re

from app.cloudforge.errors import CloudforgeError
from app.cloudforge.learn._fragment import build_graph_fragment
from app.cloudforge.learn._safety import is_unsafe_content
from app.cloudforge.learn._taxonomy import infer_domains, resolve_weakness_family
from app.cloudforge.learn.pattern_enums import (
    CloudProvider,
    SafetyClassification,
    ValidationStatus,
)
from app.cloudforge.learn.pattern_models import PatternProvenance, RawPatternRecord, RiskPattern
from app.cloudforge.learn.source_models import ReuseStatus
from app.cloudforge.models.findings import Severity

NORMALIZER_VERSION = "0.2.0"

_DEFAULT_SEVERITY: Severity = "medium"


class NormalizerError(CloudforgeError):
    """A raw record cannot be normalized (incomplete provenance, bad shape)."""


# --- provenance completeness ---------------------------------------------------

_REQUIRED_PROVENANCE_STRINGS: tuple[str, ...] = (
    "source_id",
    "source_name",
    "source_url_or_path",
    "source_license",
    "extraction_method",
    "content_hash",
    "adapter_name",
    "adapter_version",
)


def _assert_provenance_complete(provenance: PatternProvenance) -> None:
    """Fail loudly if any required provenance field is blank (design §7, §9.1)."""
    blank = [f for f in _REQUIRED_PROVENANCE_STRINGS if not getattr(provenance, f).strip()]
    if blank:
        raise NormalizerError(
            f"incomplete provenance for source {provenance.source_id!r}: blank field(s) {blank}"
        )


# --- id / resource-type normalization --------------------------------------------

_SLUG_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def _slugify(value: str) -> str:
    """Lowercase, non-alnum runs collapsed to a single ``-`` (stable, deterministic)."""
    slug = _SLUG_NON_ALNUM.sub("-", value.lower()).strip("-")
    return slug or "unknown"


def _build_id(raw: RawPatternRecord) -> str:
    return f"{_slugify(raw.source_id)}-{_slugify(raw.raw_id)}"


# --- declared raw_payload fields (FXL-96: preserve, don't drop) ------------------


def _payload_list(raw: RawPatternRecord, field: str) -> list[str]:
    """Read a declared list field from ``raw_payload``, tolerating a bare string.

    ``RawPatternRecord.raw_payload`` is typed ``dict[str, str | list[str]]``; a
    source that declares a single-item field as a scalar (rather than a one-element
    list) is still honored. Absent/wrong-shaped keys yield an empty list rather than
    raising — a source simply not declaring a field is not an error. Result is sorted
    + deduplicated for determinism.
    """
    value = raw.raw_payload.get(field)
    if isinstance(value, list):
        items = [item for item in value if item]
    elif isinstance(value, str) and value:
        items = [value]
    else:
        items = []
    return sorted(set(items))


def _declared_weakness_family(raw: RawPatternRecord) -> str | None:
    value = raw.raw_payload.get("weakness_family")
    return value if isinstance(value, str) and value else None


# --- safety classification ----------------------------------------------------

_METADATA_ONLY_LIKE: frozenset[ReuseStatus] = frozenset(
    {ReuseStatus.METADATA_ONLY, ReuseStatus.MAPPINGS_ONLY}
)
_RESTRICTED_LIKE: frozenset[ReuseStatus] = frozenset({ReuseStatus.RESTRICTED, ReuseStatus.UNKNOWN})


def _classify_safety(raw: RawPatternRecord) -> SafetyClassification:
    """Assign safety_classification from reuse_status + a content scan (design §9.1).

    The unsafe-operational content scan (``_safety.is_unsafe_content``) overrides
    every other signal: any match forces ``unsafe_operational`` regardless of how
    permissive the source's ``reuse_status`` is (design §1 hard non-goal: never
    ingest offensive/operational-attack content).
    """
    if is_unsafe_content(raw.title, raw.summary, raw.remediation):
        return SafetyClassification.UNSAFE_OPERATIONAL

    reuse_status = raw.provenance.reuse_status
    if reuse_status in _METADATA_ONLY_LIKE:
        return SafetyClassification.BENCHMARK_PATTERN
    if reuse_status in _RESTRICTED_LIKE:
        return SafetyClassification.RESTRICTED_SOURCE
    return SafetyClassification.DEFENSIVE_PATTERN


# --- normalizer --------------------------------------------------------------------


class PatternNormalizer:
    """Normalizes any adapter's ``RawPatternRecord`` into a ``RiskPattern`` (design §9.1)."""

    def normalize(self, raw: RawPatternRecord) -> RiskPattern:
        """Deterministically map ``raw`` onto the ``RiskPattern`` ontology.

        Raises ``NormalizerError`` (a ``CloudforgeError``) if ``raw.provenance`` is
        incomplete. Sets ``validation_status = unvalidated`` — a later validator
        (ticket #67) promotes it. ``training_eligible`` is never set directly: it is
        a ``computed_field`` derived by ``RiskPattern`` from the fields set here.
        """
        _assert_provenance_complete(raw.provenance)

        provenance = raw.provenance.model_copy(update={"normalizer_version": NORMALIZER_VERSION})
        resource_types = sorted(set(raw.resource_types))
        weakness_family = resolve_weakness_family(raw, _declared_weakness_family(raw))

        return RiskPattern(
            id=_build_id(raw),
            title=raw.title,
            summary=raw.summary,
            cloud_provider=raw.cloud_provider or CloudProvider.GENERIC,
            domains=infer_domains(raw),
            weakness_family=weakness_family,
            severity=raw.severity or _DEFAULT_SEVERITY,
            affected_resource_types=resource_types,
            risky_relationships=_payload_list(raw, "risky_relationships"),
            missing_controls=_payload_list(raw, "missing_controls"),
            negative_controls=_payload_list(raw, "negative_controls"),
            compensating_controls=_payload_list(raw, "compensating_controls"),
            graph_fragment=build_graph_fragment(raw),
            expected_findings=[],
            remediation=raw.remediation,
            detection_hints=[],
            control_mappings=[],
            source_mappings=sorted({raw.rule_id}) if raw.rule_id else [],
            provenance=provenance,
            confidence=raw.provenance.confidence,
            realism_score=0.0,
            quality_score=0.0,
            validation_status=ValidationStatus.UNVALIDATED,
            safety_classification=_classify_safety(raw),
        )
