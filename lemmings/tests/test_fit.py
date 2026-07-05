"""Tests for lemmings.sim.fit -- fitting SEM priors from real KPI ledgers.

Each knob is fitted only with enough observations; otherwise it is skipped and
reported (never silently dropped). On a brand-new project the override is empty
and the synthetic defaults stand.
"""

from __future__ import annotations

import math

from lemmings.sim import fit


def _ledger(agent, n, cost, dur, ticket_prefix="T"):
    return [
        {
            "agent": agent,
            "compute_cost_usd": str(cost),
            "billed_usd": "0",
            "duration_sec": str(dur),
            "ticket": f"{ticket_prefix}-{i}",
        }
        for i in range(n)
    ]


# --- cost rates -----------------------------------------------------------


def test_fit_cost_rates_basic():
    # 6 developer sessions, each $0.60 over 600s (10 min) -> $0.06/min.
    rows = _ledger("developer", 6, 0.60, 600)
    rates, skipped = fit.fit_cost_rates(rows, min_samples=5)
    assert abs(rates["developer"] - 0.06) < 1e-6
    assert "developer" not in dict(skipped)


def test_fit_cost_rates_skips_below_min_samples():
    rows = _ledger("developer", 2, 0.60, 600)
    rates, skipped = fit.fit_cost_rates(rows, min_samples=5)
    assert "developer" not in rates
    assert "developer" in dict(skipped)


def test_fit_cost_rates_skips_zero_duration():
    rows = _ledger("developer", 6, 0.60, 0)
    rates, skipped = fit.fit_cost_rates(rows, min_samples=5)
    assert "developer" not in rates


# --- bug lambda -----------------------------------------------------------


def test_fit_bug_lambda():
    # 5 distinct tickets, 10 bug rows -> lambda 2.0
    ledger = [{"agent": "developer", "compute_cost_usd": "0", "billed_usd": "0",
               "duration_sec": "60", "ticket": f"T-{i}"} for i in range(5)]
    bugs = [{"feature_ticket": f"T-{i % 5}"} for i in range(10)]
    lam, reason = fit.fit_bug_lambda(ledger, bugs, min_samples=5)
    assert lam == 2.0


def test_fit_bug_lambda_cold_start():
    ledger = [{"ticket": "T-1", "duration_sec": "60", "agent": "developer",
               "compute_cost_usd": "0", "billed_usd": "0"}]
    lam, reason = fit.fit_bug_lambda(ledger, [], min_samples=5)
    assert lam is None
    assert reason


# --- review duration ------------------------------------------------------


def test_fit_review_duration_mu():
    rows = [{"turnaround_minutes": "10"} for _ in range(5)]
    mu, reason = fit.fit_review_duration(rows, min_samples=5)
    assert abs(mu - math.log(10)) < 1e-3


def test_fit_review_duration_cold_start():
    mu, reason = fit.fit_review_duration([{"turnaround_minutes": "10"}], min_samples=5)
    assert mu is None


# --- assembly -------------------------------------------------------------


def test_fit_priors_assembles_override():
    ledger = _ledger("developer", 6, 0.60, 600)
    bugs = [{"feature_ticket": ledger[i]["ticket"]} for i in range(3)]
    reviews = [{"turnaround_minutes": "12"} for _ in range(6)]
    out = fit.fit_priors(ledger, bugs, reviews, min_samples=5)
    override = out["override"]
    assert override["agents"]["developer"]["cost_rate_per_min"] > 0
    assert "base_lambda" in override["bugs"]
    assert "duration_mu" in override["review"]
    assert out["fitted"]  # non-empty list of what was learned


def test_fit_priors_cold_start_empty_override():
    out = fit.fit_priors([], [], [], min_samples=5)
    assert out["override"] == {}
    assert out["fitted"] == []
    assert out["skipped"]  # everything reported as skipped


def test_fitted_override_is_valid_for_loader(tmp_path):
    """A fitted override must deep-merge cleanly into the validated Priors."""
    from lemmings.sim.priors import load_priors

    ledger = _ledger("developer", 6, 0.60, 600)
    out = fit.fit_priors(ledger, [], [], min_samples=5)
    path = tmp_path / "priors.override.yml"
    fit.write_override(out["override"], path)
    priors = load_priors(override_path=path)
    assert priors.agents["developer"].cost_rate_per_min > 0
