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


class PathScore(BaseModel):
    """How one labeled path was graded: the hit rule, the coverage, the full walk."""

    model_config = ConfigDict(extra="forbid")

    path_id: str
    hit: bool
    # Nodes of the best guess that are on the path, over the path length.
    found: int
    total: int
    coverage: float
    # Every path node was guessed, in order.
    full_path: bool


class GradeResult(BaseModel):
    """Hits / misses / extras. A wrong answer is still a valid grade."""

    model_config = ConfigDict(extra="forbid")

    path_hits: list[str]
    path_misses: list[str]
    finding_hits: list[str]
    finding_misses: list[str]
    extras: list[str]
    path_scores: list[PathScore] = Field(default_factory=list)
