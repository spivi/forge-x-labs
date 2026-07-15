"""``VariationSpec`` + run-manifest models — the harness layer's input/output contract.

``VariationSpec`` describes a suite of scenarios to compose and measure (families ×
scale profiles × seeds × variation axes). ``VariationConstraints`` carries the safety
defaults inherited from the stress epic: ``no_apply``/``no_credentials`` default to
``True`` and literally cannot be set to ``False`` through this model (see the
validators below) — there is no toggle to defeat, only a value to load. Nothing in
this module (or anywhere in ``app.cloudforge.variation``) shells out to
``terraform apply`` or reads cloud credentials; the harness only composes bundles
in-memory and validates/reports on them (§6 of the design doc).

``RunManifest``/``ScenarioManifestEntry`` are the run-artifact models a future
suite runner (FXL-VAR-1e) will populate — one entry per composed scenario.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ValidationStatus = Literal["pass", "fail", "aborted"]
ScannerStatus = Literal["scored", "not_scored"]
ToolMode = Literal["always", "if_available", "never"]


class VariationConstraints(BaseModel):
    """Safety defaults inherited from the stress epic (structural, not togglable)."""

    model_config = ConfigDict(extra="forbid")

    no_apply: bool = True
    no_credentials: bool = True
    max_failures_before_abort: int = 25

    @field_validator("no_apply")
    @classmethod
    def _no_apply_must_stay_true(cls, value: bool) -> bool:
        if not value:
            raise ValueError("no_apply is a structural safety default; it cannot be disabled")
        return value

    @field_validator("no_credentials")
    @classmethod
    def _no_credentials_must_stay_true(cls, value: bool) -> bool:
        if not value:
            raise ValueError(
                "no_credentials is a structural safety default; it cannot be disabled"
            )
        return value


class ValidationProfile(BaseModel):
    """Which validation/report/scanner steps a suite run performs."""

    model_config = ConfigDict(extra="forbid")

    run_validate: bool
    run_report: bool
    run_terraform_validate: ToolMode
    run_checkov: ToolMode
    run_opa: ToolMode


class VariationSpec(BaseModel):
    """A suite definition: which families/scales/seeds/axes to compose and measure."""

    model_config = ConfigDict(extra="forbid")

    families: list[str]
    seed_start: int = 0
    seed_count: int
    scale_profiles: list[str]
    variation_axes: dict[str, list[str]] = Field(default_factory=dict)
    constraints: VariationConstraints = Field(default_factory=VariationConstraints)
    validation_profile: ValidationProfile

    @field_validator("families", "scale_profiles")
    @classmethod
    def _must_be_nonempty(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("must list at least one entry")
        return value

    @field_validator("seed_count")
    @classmethod
    def _seed_count_must_be_positive(cls, value: int) -> int:
        if value < 1:
            raise ValueError("seed_count must be >= 1")
        return value


class ScenarioManifestEntry(BaseModel):
    """One composed scenario's manifest record (§9 run-output-tree contract)."""

    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    family: str
    seed: int
    scale: str
    axes: dict[str, str]
    artifact_dir: str
    gen_duration_sec: float
    validation_status: ValidationStatus
    scanner_status: ScannerStatus
    failure_id: str | None = None


class RunManifest(BaseModel):
    """The whole suite run's manifest: one entry per composed scenario."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    entries: list[ScenarioManifestEntry] = Field(default_factory=list)
