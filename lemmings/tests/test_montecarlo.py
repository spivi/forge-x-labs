"""Smoke tests for the Monte Carlo sweep runner."""

from __future__ import annotations

from pathlib import Path

import pytest

scipy = pytest.importorskip("scipy")
joblib = pytest.importorskip("joblib")

from lemmings.scenarios.review_loop import build  # noqa: E402
from lemmings.sim.montecarlo import (  # noqa: E402
    ParameterSweep,
    _apply_knobs,
    records_to_csv,
    run_sweep,
)
from lemmings.sim.priors import load_default_priors  # noqa: E402


def test_apply_knobs_rounds_ints() -> None:
    priors = load_default_priors()
    _apply_knobs(priors, {"retry.max_attempts": 2.7})
    assert priors.retry.max_attempts == 3


def test_apply_knobs_floats_passthrough() -> None:
    priors = load_default_priors()
    _apply_knobs(priors, {"budget.hard_cap_factor": 1.5})
    assert priors.budget.hard_cap_factor == 1.5


def test_apply_knobs_dict_path() -> None:
    priors = load_default_priors()
    _apply_knobs(priors, {"agents.code_reviewer.false_positive_rate": 0.42})
    assert priors.agents["code_reviewer"].false_positive_rate == 0.42


def test_run_sweep_yields_m_times_k_runs() -> None:
    sweep = ParameterSweep(
        name="t",
        knobs={"retry.max_attempts": (1.0, 3.0)},
        points=4,
        seeds_per_point=2,
        sampler_seed=42,
    )
    # n_jobs=1 keeps test deterministic and easy to debug
    records = run_sweep(build, sweep, n_jobs=1)
    assert len(records) == 8
    for r in records:
        assert 1 <= int(r.params["retry.max_attempts"]) <= 3
        assert "total_billed_usd" in r.metrics
        assert r.metrics["cycle_time_min"] > 0


def test_run_sweep_metrics_vary_with_max_attempts() -> None:
    """As `retry.max_attempts` rises, total billed cost (rework cycles) rises too.

    Smoke check: average cost at max_attempts=1 should be strictly less than at
    max_attempts=5 — the review_loop scenario forces every review to FAIL, so
    higher caps mean more developer/reviewer cycles before escalation.
    """
    knobs = {"retry.max_attempts": (1.0, 5.0)}
    sweep = ParameterSweep(
        name="t",
        knobs=knobs,
        points=8,
        seeds_per_point=4,
        sampler_seed=7,
    )
    records = run_sweep(build, sweep, n_jobs=1)
    cap_key = "retry.max_attempts"
    low = [r.metrics["total_billed_usd"] for r in records if r.params[cap_key] < 2.0]
    high = [r.metrics["total_billed_usd"] for r in records if r.params[cap_key] >= 4.0]
    assert low and high, "QMC sample didn't span the range"
    assert sum(low) / len(low) < sum(high) / len(high)


def test_records_to_csv_round_trip(tmp_path: Path) -> None:
    sweep = ParameterSweep(
        name="t",
        knobs={"retry.max_attempts": (1.0, 3.0)},
        points=2,
        seeds_per_point=1,
        sampler_seed=1,
    )
    records = run_sweep(build, sweep, n_jobs=1)
    out = tmp_path / "sweep.csv"
    records_to_csv(records, out)
    text = out.read_text()
    lines = text.strip().splitlines()
    assert len(lines) == 1 + len(records)  # header + rows
    assert lines[0].startswith("scenario,seed,retry.max_attempts,")
