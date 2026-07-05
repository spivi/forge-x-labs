"""Latent factor SEM sampler.

Five of eleven correlations baked in for v1:

    #1  cost ≈ duration · model_rate + noise           (mechanical)
    #2  bugs ~ Poisson(λ · complexity · novelty)       (size-effect)
    #4  violations ~ NegBin(α·lines + β·bugs)          (two contributions)
    #6  reviewer.verdict = FAIL ⟺ violations > θ       (policy-driven)
    #10 cycle_time = Σ stages + retries · overhead     (composition; in world)

All randomness flows through hidden ticket / agent / process latents.
The `Random` instance is injected so seed-based determinism holds.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from random import Random

from lemmings.schemas import ReviewVerdict
from lemmings.sim.priors import Priors


@dataclass(frozen=True)
class TicketLatents:
    complexity: float
    novelty: float
    lines_planned: int


@dataclass(frozen=True)
class DeveloperOutcome:
    duration_min: float
    bugs_introduced: int
    lines_added: int
    cost_usd: float


@dataclass(frozen=True)
class ReviewOutcome:
    duration_min: float
    violations: int
    verdict: ReviewVerdict
    cost_usd: float


def _poisson(rng: Random, lam: float) -> int:
    """Knuth's algorithm — fine for small λ, no scipy dependency."""
    if lam <= 0:
        return 0
    threshold = math.exp(-lam)
    k = 0
    p = 1.0
    while True:
        k += 1
        p *= rng.random()
        if p <= threshold:
            return k - 1


def sample_ticket_latents(rng: Random, priors: Priors) -> TicketLatents:
    """Draw `complexity`, `novelty`, `lines_planned` from ticket priors."""
    p = priors.ticket
    complexity = max(0.1, rng.gauss(p.complexity_mean, p.complexity_sd))
    novelty = rng.betavariate(p.novelty_alpha, p.novelty_beta)
    lines_planned = max(1, int(rng.gauss(p.lines_planned_mean, p.lines_planned_sd)))
    return TicketLatents(complexity=complexity, novelty=novelty, lines_planned=lines_planned)


def sample_developer_quality_today(rng: Random, priors: Priors) -> float:
    """Process latent — shared across stages of a single ticket-run."""
    return rng.gauss(0.0, priors.process.developer_quality_sd)


def sample_developer_outcome(
    rng: Random,
    priors: Priors,
    latents: TicketLatents,
    developer_quality_today: float,
) -> DeveloperOutcome:
    """Sample developer stage. Bugs depend on complexity*novelty / skill, with
    a shared `developer_quality_today` shock that propagates to violations.
    """
    skill = priors.agents["developer"].skill
    rate = priors.agents["developer"].cost_rate_per_min

    # #2 + #3: bugs ~ Poisson(λ · complexity · novelty / skill)
    lam = (
        priors.bugs.base_lambda
        * (1.0 + priors.bugs.complexity_coef * latents.complexity)
        * (1.0 + priors.bugs.novelty_coef * latents.novelty)
        / max(0.1, skill)
    )
    # quality shock: lower quality today → more bugs
    lam *= math.exp(-developer_quality_today)
    bugs = _poisson(rng, lam)

    # duration ~ LogNormal(μ + δ·log(lines), σ)
    d = priors.developer
    mu = d.duration_mu + d.duration_lines_coef * math.log(max(1, latents.lines_planned))
    duration = math.exp(rng.gauss(mu, d.duration_sigma))

    # actual lines = planned + small noise
    lines_added = max(1, int(rng.gauss(latents.lines_planned, latents.lines_planned * 0.1)))

    # #1: cost = duration · rate · (1 + noise)
    cost = duration * rate * (1.0 + rng.gauss(0.0, 0.05))

    return DeveloperOutcome(
        duration_min=duration,
        bugs_introduced=bugs,
        lines_added=lines_added,
        cost_usd=max(0.0, cost),
    )


def sample_review_outcome(
    rng: Random,
    priors: Priors,
    lines_added: int,
    bugs: int,
    developer_quality_today: float,
) -> ReviewOutcome:
    """Sample reviewer stage. Violations come from lines + bugs (correlation
    #4). Verdict is policy-driven: FAIL ⟺ violations > threshold (#6).
    """
    rate = priors.agents["code_reviewer"].cost_rate_per_min
    fp_rate = priors.agents["code_reviewer"].false_positive_rate

    # #4: violations ~ NegBin(α·lines + β·bugs)
    # Approximated as max(0, round(Normal(mean, sqrt(mean·dispersion)))).
    mean = (
        priors.violations.alpha_per_line * lines_added
        + priors.violations.beta_per_bug * bugs
    )
    # quality shock propagates: low-quality day → more violations (shared cause #8)
    mean *= math.exp(-developer_quality_today)
    sd = max(1.0, math.sqrt(max(0.5, mean) + priors.violations.noise_sd**2))
    violations = max(0, int(round(rng.gauss(mean, sd))))

    # false-positive flips: a clean PR sometimes gets flagged anyway
    if violations <= priors.review.violation_threshold and rng.random() < fp_rate:
        violations = priors.review.violation_threshold + 1

    # #5: review duration ~ LogNormal(μ + δ·log(lines), σ)
    r = priors.review
    mu = r.duration_mu + r.duration_lines_coef * math.log(max(1, lines_added))
    duration = math.exp(rng.gauss(mu, r.duration_sigma))

    # #6: verdict policy
    if violations > priors.review.violation_threshold:
        verdict = ReviewVerdict.FAIL
    else:
        verdict = ReviewVerdict.PASS

    cost = duration * rate * (1.0 + rng.gauss(0.0, 0.05))

    return ReviewOutcome(
        duration_min=duration,
        violations=violations,
        verdict=verdict,
        cost_usd=max(0.0, cost),
    )
