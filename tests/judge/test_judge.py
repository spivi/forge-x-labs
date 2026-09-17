"""Jev rationale judge: code owns thresholds; the client is injected."""

from __future__ import annotations

from types import SimpleNamespace

from app.cloudforge.generate.ci_cd_iam_chain import (
    build_findings,
    build_graph,
    build_ground_truth,
)
from app.cloudforge.judge.compose import compose_verdict
from app.cloudforge.judge.engine import judge_rationale
from app.cloudforge.judge.state import build_judge_state


def _response(*, entry: float, hop: float, sink: float, score: float) -> SimpleNamespace:
    return SimpleNamespace(
        nouls={
            "names_entry": SimpleNamespace(noul=entry),
            "names_identity_hop": SimpleNamespace(noul=hop),
            "names_sink": SimpleNamespace(noul=sink),
        },
        scores={"completeness": SimpleNamespace(score=score, confidence=0.9)},
    )


def test_state_uses_ground_truth_hop_names() -> None:
    state = build_judge_state(
        "the deploy role can pass the runtime role",
        build_graph(),
        build_findings(),
        build_ground_truth(),
    )
    assert state["ground_truth"]["entry_name"]
    assert state["ground_truth"]["sink_name"]
    assert "DeployRole" in state["ground_truth"]["hop_names"]


def test_compose_hit_when_all_hops_are_high() -> None:
    verdict = compose_verdict(_response(entry=0.9, hop=0.85, sink=0.92, score=2), "jev-latest")
    assert verdict.semantic_hit is True
    assert verdict.needs_review is False


def test_compose_review_when_noul_is_uncertain() -> None:
    verdict = compose_verdict(_response(entry=0.51, hop=0.9, sink=0.9, score=1), "jev-latest")
    assert verdict.semantic_hit is False
    assert verdict.needs_review is True


class _FakeClient:
    def __init__(self, response: SimpleNamespace) -> None:
        self.response = response
        self.calls: list[tuple[object, object]] = []

    def system_one(self, state: object, questions: object) -> SimpleNamespace:
        self.calls.append((state, questions))
        return self.response


def test_engine_uses_injected_client() -> None:
    client = _FakeClient(_response(entry=0.8, hop=0.8, sink=0.8, score=2))
    verdict = judge_rationale(
        "OIDC identity assumes DeployRole, which passes RuntimeRole into customer-exports",
        build_graph(),
        build_findings(),
        build_ground_truth(),
        client,
    )
    assert verdict.semantic_hit is True
    assert client.calls
    assert "names_entry" in client.calls[0][1]
