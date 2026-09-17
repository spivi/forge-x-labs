"""Atomic Jev questions: does the writeup name the labeled chain?"""

from __future__ import annotations

from typing import Any


def judge_questions() -> dict[str, Any]:
    """Narrow Noul/Score questions over `student.rationale` vs ground truth."""
    from typesafe_sdk import Noul, Score

    return {
        "names_entry": Noul(
            instructions=(
                "Does `student.rationale` identify the same initial access "
                "as `ground_truth.entry_name`?"
            ),
        ),
        "names_identity_hop": Noul(
            instructions=(
                "Does `student.rationale` describe the identity or role hop "
                "named in `ground_truth.identity_hop`?"
            ),
        ),
        "names_sink": Noul(
            instructions=(
                "Does `student.rationale` identify the same sensitive data sink "
                "as `ground_truth.sink_name`?"
            ),
        ),
        "completeness": Score(
            instructions=(
                "How complete is `student.rationale` relative to `ground_truth.explanation`?"
            ),
            criteria=[
                "Names a different risk, or none of the critical hops",
                "Names the sink or the entry but not the connecting hop",
                "Names the entry, the identity hop, and the sink",
            ],
        ),
    }
