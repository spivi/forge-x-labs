"""SEM self-tests — sample correlations match design targets.

Each test runs N independent draws and checks summary stats. These
keep the latent model honest as priors evolve.
"""

from __future__ import annotations

import math
from random import Random
from statistics import mean

from lemmings.schemas import ReviewVerdict
from lemmings.sim.latents import (
    sample_developer_outcome,
    sample_developer_quality_today,
    sample_review_outcome,
    sample_ticket_latents,
)
from lemmings.sim.priors import load_default_priors

N = 2000


def _pearson(xs: list[float], ys: list[float]) -> float:
    mx = mean(xs)
    my = mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx == 0 or dy == 0:
        return 0.0
    return num / (dx * dy)


def test_correlation_1_cost_tracks_duration() -> None:
    """#1 cost ≈ duration · model_rate + noise."""
    priors = load_default_priors()
    rng = Random(7)
    durations: list[float] = []
    costs: list[float] = []
    for _ in range(N):
        latents = sample_ticket_latents(rng, priors)
        q = sample_developer_quality_today(rng, priors)
        outcome = sample_developer_outcome(rng, priors, latents, q)
        durations.append(outcome.duration_min)
        costs.append(outcome.cost_usd)
    r = _pearson(durations, costs)
    assert r > 0.95, f"cost-duration correlation too weak: {r:.3f}"


def test_correlation_2_bugs_track_complexity_x_novelty() -> None:
    """#2 bugs ~ Poisson(λ · complexity · novelty)."""
    priors = load_default_priors()
    rng = Random(11)
    cn: list[float] = []
    bugs: list[float] = []
    for _ in range(N):
        latents = sample_ticket_latents(rng, priors)
        q = sample_developer_quality_today(rng, priors)
        outcome = sample_developer_outcome(rng, priors, latents, q)
        cn.append(latents.complexity * latents.novelty)
        bugs.append(float(outcome.bugs_introduced))
    r = _pearson(cn, bugs)
    assert r > 0.10, f"bugs-(complexity·novelty) correlation too weak: {r:.3f}"


def test_correlation_4_violations_track_lines_and_bugs() -> None:
    """#4 violations ~ NegBin(α·lines + β·bugs)."""
    priors = load_default_priors()
    rng = Random(17)
    means: list[float] = []
    violations: list[float] = []
    for _ in range(N):
        lines = rng.randint(50, 500)
        bugs = rng.randint(0, 10)
        out = sample_review_outcome(
            rng, priors, lines_added=lines, bugs=bugs, developer_quality_today=0.0
        )
        means.append(
            priors.violations.alpha_per_line * lines + priors.violations.beta_per_bug * bugs
        )
        violations.append(float(out.violations))
    r = _pearson(means, violations)
    assert r > 0.5, f"violations-(α·lines+β·bugs) correlation too weak: {r:.3f}"


def test_correlation_6_verdict_policy() -> None:
    """#6 reviewer.verdict = FAIL ⟺ violations > threshold (deterministic
    given violations and threshold; check it holds in the sampler too)."""
    priors = load_default_priors()
    rng = Random(23)
    threshold = priors.review.violation_threshold
    for _ in range(N):
        out = sample_review_outcome(
            rng,
            priors,
            lines_added=rng.randint(50, 500),
            bugs=rng.randint(0, 10),
            developer_quality_today=0.0,
        )
        if out.violations > threshold:
            assert out.verdict is ReviewVerdict.FAIL
        else:
            assert out.verdict is ReviewVerdict.PASS
