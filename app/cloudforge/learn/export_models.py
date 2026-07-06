"""Training-export result models (design §9.6): the bundle + its manifest.

Kept separate from ``pattern_models.py`` (that module is scoped to the ``RiskPattern``
ontology itself, not export-time reporting) and separate from ``export.py`` to keep
every module under the 200-line cap (rules/general.md).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.cloudforge.learn.pattern_models import RiskPattern

EXPORT_RULESET: tuple[str, ...] = (
    "validation_status == valid",
    "training_eligible == true",
    "safety_classification in {defensive_pattern, benchmark_pattern, training_pattern}",
    "provenance.reuse_status allows reuse (full_reuse or attribution, "
    "or mappings_only per FXL-D007)",
    "provenance.allowed_for_training == true",
    "quality_score >= 0.70",
)

EXPORT_FORMAT_VERSION = "1.0.0"


class ExclusionBreakdown(BaseModel):
    """Counts of excluded patterns, keyed by exclusion reason."""

    model_config = ConfigDict(extra="forbid")

    not_training_eligible: int = 0
    below_quality_bar: int = 0
    unsafe_operational: int = 0
    restricted_source_excluded: int = 0

    @property
    def total(self) -> int:
        """Sum of every reason bucket (a pattern may only match one bucket)."""
        return (
            self.not_training_eligible
            + self.below_quality_bar
            + self.unsafe_operational
            + self.restricted_source_excluded
        )


class TrainingExportManifest(BaseModel):
    """Coverage + ruleset manifest for a :class:`TrainingExport` (design §9.6)."""

    model_config = ConfigDict(extra="forbid")

    version: str
    total_input: int
    exported_count: int
    excluded_count: int
    excluded_breakdown: ExclusionBreakdown
    provider_coverage: dict[str, int]
    domain_coverage: dict[str, int]
    weakness_family_coverage: dict[str, int]
    quality_bar: float
    ruleset: list[str]
    include_restricted: bool
    restricted_admitted_count: int


class TrainingExport(BaseModel):
    """A pure in-memory export result: the exported records + their manifest.

    ``export_training`` builds this with no I/O; :func:`write_training_export`
    (in ``export.py``) is the only place that touches the filesystem.
    """

    model_config = ConfigDict(extra="forbid")

    manifest: TrainingExportManifest
    records: list[RiskPattern]
