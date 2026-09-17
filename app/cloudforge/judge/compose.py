"""Combine Jev probabilities in code. Thresholds are ours, not the model's."""

from __future__ import annotations

from typing import Any

from app.cloudforge.judge.models import JudgeVerdict

_HIT = 0.7
_UNCERTAIN_LOW = 0.4
_UNCERTAIN_HIGH = 0.6


def compose_verdict(response: Any, model: str) -> JudgeVerdict:
    """semantic_hit requires all three hops; mid-probability Nouls need review."""
    entry = float(response.nouls["names_entry"].noul)
    hop = float(response.nouls["names_identity_hop"].noul)
    sink = float(response.nouls["names_sink"].noul)
    completeness = response.scores["completeness"]
    score_val = float(completeness.score)
    labels = (
        "Names a different risk, or none of the critical hops",
        "Names the sink or the entry but not the connecting hop",
        "Names the entry, the identity hop, and the sink",
    )
    idx = min(2, max(0, int(round(score_val))))
    label = labels[idx]
    uncertain = any(_UNCERTAIN_LOW < p < _UNCERTAIN_HIGH for p in (entry, hop, sink))
    return JudgeVerdict(
        names_entry=entry,
        names_identity_hop=hop,
        names_sink=sink,
        completeness=score_val,
        completeness_label=label,
        semantic_hit=entry >= _HIT and hop >= _HIT and sink >= _HIT,
        needs_review=uncertain,
        model=model,
    )
