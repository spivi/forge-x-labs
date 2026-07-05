"""``PatternNormalizer``: ``RawPatternRecord`` -> ``RiskPattern`` (design §9.1).

Maps adapter-specific fields onto the ontology (design §6), sorts every list field
for determinism, builds/verifies the ``graph_fragment`` as a real ``ScenarioGraph``
(reusing the existing model — its ``model_validator`` already checks edge endpoints
resolve), assigns ``safety_classification`` from the source's ``reuse_status`` plus a
conservative keyword/secret content scan, stamps provenance completely (raising a
clear ``CloudforgeError`` on incomplete provenance), and pins ``normalizer_version``.
``validation_status`` is always set to ``unvalidated`` here — the later validator
(ticket #67) promotes it to ``valid``/``invalid``. ``training_eligible`` is left
untouched: it is a ``computed_field`` derived by ``RiskPattern`` itself.

No ML, no embeddings — pure deterministic field mapping (guiding directive, design §1).
"""

from __future__ import annotations

import re

from app.cloudforge.errors import CloudforgeError
from app.cloudforge.learn._safety import is_unsafe_content
from app.cloudforge.learn._taxonomy import infer_domains, infer_weakness_family
from app.cloudforge.learn.pattern_enums import (
    CloudProvider,
    SafetyClassification,
    ValidationStatus,
)
from app.cloudforge.learn.pattern_models import PatternProvenance, RawPatternRecord, RiskPattern
from app.cloudforge.learn.source_models import ReuseStatus
from app.cloudforge.models.findings import Severity
from app.cloudforge.models.graph import GraphNode, NodeSecurity, NodeTags, NodeType, ScenarioGraph

NORMALIZER_VERSION = "0.1.0"

_DEFAULT_SEVERITY: Severity = "medium"
_FRAGMENT_NODE_TAGS = NodeTags(env="unknown", owner="unknown", app="unknown")
_FRAGMENT_NODE_SECURITY = NodeSecurity(criticality="medium")


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


# --- graph fragment ---------------------------------------------------------------


def _minimal_fragment(resource_types: list[str]) -> ScenarioGraph:
    """Build a minimal fragment: one generic node per (deduped, sorted) resource type.

    No relationships are known from a bare resource-type list, so no edges are
    emitted — an edge-less fragment is a valid ``ScenarioGraph`` (nothing to resolve).
    """
    nodes = [
        GraphNode(
            id=f"resource-{index}",
            type=NodeType.APPLICATION,
            name=resource_type,
            tags=_FRAGMENT_NODE_TAGS,
            security=_FRAGMENT_NODE_SECURITY,
            attributes={"resource_type": resource_type},
        )
        for index, resource_type in enumerate(sorted(set(resource_types)))
    ]
    return ScenarioGraph(nodes=nodes, edges=[])


def _fragment_from_raw_payload(raw: RawPatternRecord) -> ScenarioGraph | None:
    """Reuse a real, already-validated graph embedded in ``raw_payload`` (design §9.1).

    The ``cloudforge_scenario`` adapter stores the full scenario graph as a
    JSON-encoded string under ``raw_payload["graph"]``; when present it is a richer,
    real fragment (with edges) and should be reused verbatim rather than rebuilt.
    """
    graph_json = raw.raw_payload.get("graph")
    if not isinstance(graph_json, str) or not graph_json:
        return None
    return ScenarioGraph.model_validate_json(graph_json)


def _build_graph_fragment(raw: RawPatternRecord) -> ScenarioGraph:
    embedded = _fragment_from_raw_payload(raw)
    if embedded is not None:
        return embedded
    return _minimal_fragment(raw.resource_types)


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

        return RiskPattern(
            id=_build_id(raw),
            title=raw.title,
            summary=raw.summary,
            cloud_provider=raw.cloud_provider or CloudProvider.GENERIC,
            domains=infer_domains(raw),
            weakness_family=infer_weakness_family(raw),
            severity=raw.severity or _DEFAULT_SEVERITY,
            affected_resource_types=resource_types,
            risky_relationships=[],
            missing_controls=[],
            negative_controls=[],
            compensating_controls=[],
            graph_fragment=_build_graph_fragment(raw),
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
