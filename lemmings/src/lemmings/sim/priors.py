"""Pydantic-validated priors loader.

Loads `priors_default.yml` shipped with the package; an override path
(e.g. `shopping_agent/.dev-context/sim/priors.override.yml`) may be
deep-merged on top.
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class AgentPrior(BaseModel):
    skill: float = 1.0
    cost_rate_per_min: float = 0.05
    false_positive_rate: float = 0.0


class TicketPriors(BaseModel):
    complexity_mean: float = 1.0
    complexity_sd: float = 0.4
    novelty_alpha: float = 2.0
    novelty_beta: float = 5.0
    lines_planned_mean: float = 150.0
    lines_planned_sd: float = 80.0


class BugPriors(BaseModel):
    base_lambda: float = 0.5
    complexity_coef: float = 1.0
    novelty_coef: float = 1.5


class ViolationPriors(BaseModel):
    alpha_per_line: float = 0.02
    beta_per_bug: float = 1.5
    noise_sd: float = 1.0


class DurationPriors(BaseModel):
    duration_mu: float
    duration_lines_coef: float
    duration_sigma: float


class ReviewPriors(DurationPriors):
    violation_threshold: int = 5


class ProcessPriors(BaseModel):
    developer_quality_sd: float = 0.3


class BudgetPriors(BaseModel):
    sprint_budget_usd: float = 50.0
    hard_cap_factor: float = 1.2


class RetryPriors(BaseModel):
    max_attempts: int = 3


class Priors(BaseModel):
    agents: dict[str, AgentPrior] = Field(default_factory=dict)
    ticket: TicketPriors = Field(default_factory=TicketPriors)
    bugs: BugPriors = Field(default_factory=BugPriors)
    violations: ViolationPriors = Field(default_factory=ViolationPriors)
    review: ReviewPriors
    developer: DurationPriors
    process: ProcessPriors = Field(default_factory=ProcessPriors)
    budget: BudgetPriors = Field(default_factory=BudgetPriors)
    retry: RetryPriors = Field(default_factory=RetryPriors)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, val in override.items():
        if key in out and isinstance(out[key], dict) and isinstance(val, dict):
            out[key] = _deep_merge(out[key], val)
        else:
            out[key] = val
    return out


def load_default_priors() -> Priors:
    raw = resources.files("lemmings").joinpath("priors_default.yml").read_text()
    return Priors.model_validate(yaml.safe_load(raw))


def load_priors(override_path: Path | None = None) -> Priors:
    raw = resources.files("lemmings").joinpath("priors_default.yml").read_text()
    data: dict[str, Any] = yaml.safe_load(raw)
    if override_path is not None:
        override = yaml.safe_load(override_path.read_text()) or {}
        data = _deep_merge(data, override)
    return Priors.model_validate(data)
