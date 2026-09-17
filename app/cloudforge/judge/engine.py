"""Call Jev. Core grade stays local; this is opt-in when an API key is set."""

from __future__ import annotations

import os
from typing import Any

from app.cloudforge.errors import CloudforgeError
from app.cloudforge.judge.compose import compose_verdict
from app.cloudforge.judge.models import JudgeVerdict
from app.cloudforge.judge.questions import judge_questions
from app.cloudforge.judge.state import build_judge_state
from app.cloudforge.models.findings import ExpectedFindings, GroundTruthPaths
from app.cloudforge.models.graph import ScenarioGraph

_MODEL = "jev-latest"


def judge_rationale(
    rationale: str,
    graph: ScenarioGraph,
    findings: ExpectedFindings,
    paths: GroundTruthPaths,
    client: Any | None = None,
) -> JudgeVerdict:
    """Ask Jev whether a free-text writeup names the labeled attack chain."""
    if not rationale.strip():
        raise CloudforgeError("rationale is empty")
    state = build_judge_state(rationale, graph, findings, paths)
    runner = client if client is not None else _live_client()
    response = runner.system_one(state, judge_questions())
    return compose_verdict(response, _MODEL)


def _live_client() -> Any:
    key = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if not key:
        raise CloudforgeError("TYPESAFE_API_KEY is not set; cloudforge judge is opt-in")
    try:
        from typesafe_sdk import TypeSafeClient
    except ImportError as exc:
        raise CloudforgeError("typesafe-sdk is not installed") from exc
    return TypeSafeClient(api_key=key, model=_MODEL)
