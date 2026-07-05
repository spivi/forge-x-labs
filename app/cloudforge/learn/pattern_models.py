"""The RiskPattern ontology — the normalized unit of the learning corpus.

A ``RiskPattern`` is compatible with the product's existing graph model: its
``graph_fragment`` is a ``ScenarioGraph`` and its ``expected_findings`` reuse the
existing ``ExpectedFinding`` / ``Severity`` types. Every pattern carries exactly one
``PatternProvenance`` — **no provenance, no corpus** (design §7).

``training_eligible`` is DERIVED, not free-form (design §6, honoring FXL-D007): a
pattern is eligible iff it is valid, safely classified, its provenance allows training,
and its ``reuse_status`` is not restricted/metadata_only/unknown. ``mappings_only``
(CCM control-ID mappings) IS allowed.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.cloudforge.learn.pattern_enums import (
    TRAINABLE_CLASSIFICATIONS,
    CloudProvider,
    Domain,
    SafetyClassification,
    ValidationStatus,
    WeaknessFamily,
)
from app.cloudforge.learn.source_models import NON_TRAINING_REUSE, ReuseStatus, SourceType
from app.cloudforge.models.findings import ExpectedFinding, Severity
from app.cloudforge.models.graph import ScenarioGraph

# Re-exported so callers may import every ontology name from ``pattern_models`` too.
__all__ = [
    "TRAINABLE_CLASSIFICATIONS",
    "CloudProvider",
    "Domain",
    "PatternProvenance",
    "RawPatternRecord",
    "RiskPattern",
    "SafetyClassification",
    "ValidationStatus",
    "WeaknessFamily",
]


class PatternProvenance(BaseModel):
    """Where a pattern came from — required on every ``RiskPattern`` (design §7).

    Timestamps are ``datetime`` and are always passed in (the repo avoids
    ``datetime.now()`` at import/default time for determinism).
    """

    model_config = ConfigDict(extra="forbid")

    source_id: str
    source_name: str
    source_type: SourceType
    source_url_or_path: str
    source_license: str
    reuse_status: ReuseStatus
    allowed_for_training: bool
    extraction_method: str
    fetched_at: datetime
    extracted_at: datetime
    content_hash: str
    adapter_name: str
    adapter_version: str
    normalizer_version: str
    confidence: float = Field(ge=0.0, le=1.0)
    notes: str = ""


class RawPatternRecord(BaseModel):
    """Adapter output — minimally structured, pre-normalization (design §8).

    Adapters (later tickets) emit these; the normalizer (later) turns each into a
    ``RiskPattern``. Kept loose on purpose: only ``source_id`` and ``provenance`` are
    load-bearing here.
    """

    model_config = ConfigDict(extra="forbid")

    source_id: str
    raw_id: str
    title: str
    summary: str = ""
    cloud_provider: CloudProvider | None = None
    resource_types: list[str] = Field(default_factory=list)
    rule_id: str | None = None
    severity: Severity | None = None
    category: str | None = None
    remediation: str = ""
    references: list[str] = Field(default_factory=list)
    raw_payload: dict[str, str | list[str]] = Field(default_factory=dict)
    provenance: PatternProvenance


class RiskPattern(BaseModel):
    """The normalized corpus unit (design §6). ``graph_fragment`` is a ``ScenarioGraph``."""

    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    summary: str
    cloud_provider: CloudProvider
    domains: list[Domain]
    weakness_family: WeaknessFamily
    severity: Severity
    affected_resource_types: list[str] = Field(default_factory=list)
    risky_relationships: list[str] = Field(default_factory=list)
    missing_controls: list[str] = Field(default_factory=list)
    negative_controls: list[str] = Field(default_factory=list)
    compensating_controls: list[str] = Field(default_factory=list)
    graph_fragment: ScenarioGraph
    expected_findings: list[ExpectedFinding] = Field(default_factory=list)
    remediation: str = ""
    detection_hints: list[str] = Field(default_factory=list)
    control_mappings: list[str] = Field(default_factory=list)
    source_mappings: list[str] = Field(default_factory=list)
    provenance: PatternProvenance
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    realism_score: float = Field(default=0.0, ge=0.0, le=1.0)
    quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    validation_status: ValidationStatus = ValidationStatus.UNVALIDATED
    safety_classification: SafetyClassification = SafetyClassification.UNKNOWN

    @computed_field  # type: ignore[prop-decorator]
    @property
    def training_eligible(self) -> bool:
        """Derived eligibility (design §6, FXL-D007).

        Eligible iff validated AND safely classified AND provenance allows training AND
        the reuse_status is not restricted/metadata_only/unknown. ``mappings_only`` and
        ``full_reuse``/``attribution`` are allowed.
        """
        return (
            self.validation_status is ValidationStatus.VALID
            and self.safety_classification in TRAINABLE_CLASSIFICATIONS
            and self.provenance.allowed_for_training
            and self.provenance.reuse_status not in NON_TRAINING_REUSE
        )
