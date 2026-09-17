"""Pydantic models for a student guess and a grade result."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PathGuess(BaseModel):
    """Ordered node ids the student believes form a risk path."""

    model_config = ConfigDict(extra="forbid")

    nodes: list[str]


class LabSubmission(BaseModel):
    """What ``cloudforge grade`` reads from the student's YAML."""

    model_config = ConfigDict(extra="forbid")

    paths: list[PathGuess] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)
    rationale: str | None = None


class GradeResult(BaseModel):
    """Hits / misses / extras. A wrong answer is still a valid grade."""

    model_config = ConfigDict(extra="forbid")

    path_hits: list[str]
    path_misses: list[str]
    finding_hits: list[str]
    finding_misses: list[str]
    extras: list[str]
