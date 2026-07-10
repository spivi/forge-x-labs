"""The scenario input model — user intent, validated on load.

Mirrors ``examples/*.yaml``. A validator enforces the hard MVP boundary that a
generated scenario is never deployable.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CompanyProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    size: str
    app_name: str


class Requirements(BaseModel):
    model_config = ConfigDict(extra="forbid")

    critical_chains: int
    medium_findings: int
    false_positives: int


class Constraints(BaseModel):
    model_config = ConfigDict(extra="forbid")

    no_real_secrets: bool
    no_destructive_permissions: bool
    max_resources: int
    deployable: bool

    @field_validator("deployable")
    @classmethod
    def _must_not_be_deployable(cls, value: bool) -> bool:
        if value:
            raise ValueError("MVP scenarios must set deployable: false (never deployed)")
        return value


class ScenarioSpec(BaseModel):
    """A validated scenario definition (the ``scenario.yaml`` contract)."""

    model_config = ConfigDict(extra="forbid")

    cloud: Literal["aws"]
    scenario_type: str
    environment: str
    difficulty: str
    company_profile: CompanyProfile
    requirements: Requirements
    constraints: Constraints
    scale_profile: str = "small"
    variation_axes: dict[str, str] = Field(default_factory=dict)

    @field_validator("variation_axes")
    @classmethod
    def _axes_must_be_int_coercible(cls, axes: dict[str, str]) -> dict[str, str]:
        for key, value in axes.items():
            try:
                int(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"variation_axes[{key!r}] must be an integer count, got {value!r}"
                ) from exc
        return axes
