"""Typed verdict for a student rationale judged against ground truth."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class JudgeVerdict(BaseModel):
    """Probabilities from Jev, composed in code into a hit / review flag."""

    model_config = ConfigDict(extra="forbid")

    names_entry: float
    names_identity_hop: float
    names_sink: float
    completeness: float
    completeness_label: str
    semantic_hit: bool
    needs_review: bool
    model: str
