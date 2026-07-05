"""Monte Carlo runner — quasi-random parameter sweeps over scenarios.

A "sweep" draws M parameter points from a quasi-random sequence (Latin
Hypercube or Sobol) and runs each point against K independent seeds.
The default M=64, K=10 ⇒ 640 sims, parallelised with joblib.

Each run yields a `RunRecord` with a `metrics` dict; aggregate however
you like (groupby on params, take mean / p50 / p95). No pandas dep —
emit CSV with `records_to_csv`.

Knobs are dotted paths into `Priors`. `agents` is a dict, the rest are
attributes — the walker handles both. Integer-typed knobs (e.g.
`retry.max_attempts`) are rounded.

Requires the `mc` extra: `pip install -e .[mc]`.

Usage:
    sweep = ParameterSweep(
        name="retry_cap_vs_cost",
        knobs={
            "retry.max_attempts": (1, 5),
            "budget.hard_cap_factor": (1.0, 2.0),
        },
        points=32, seeds_per_point=10,
    )
    from lemmings.scenarios.review_loop import build as build_review
    records = run_sweep(build_review, sweep)
    records_to_csv(records, Path("/tmp/sweep.csv"))
"""

from __future__ import annotations

import csv
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from joblib import Parallel, delayed
from scipy.stats import qmc

from lemmings.sim.priors import Priors, load_default_priors
from lemmings.sim.scenario import Scenario, run_scenario


@dataclass
class ParameterSweep:
    """A quasi-random sweep over a subset of `Priors` knobs.

    `knobs` maps dotted paths (e.g. `retry.max_attempts`,
    `agents.code_reviewer.false_positive_rate`) to (low, high) ranges.
    """

    name: str
    knobs: dict[str, tuple[float, float]]
    points: int = 64
    seeds_per_point: int = 10
    sampler: Literal["lhs", "sobol"] = "lhs"
    sampler_seed: int = 0


@dataclass
class RunRecord:
    scenario: str
    seed: int
    params: dict[str, float]
    metrics: dict[str, float] = field(default_factory=dict)


# --- knob walker ---


def _walk_to_parent(obj: Any, parts: list[str]) -> Any:
    cur = obj
    for part in parts:
        cur = cur[part] if isinstance(cur, dict) else getattr(cur, part)
    return cur


def _set_at(parent: Any, key: str, value: Any) -> None:
    if isinstance(parent, dict):
        parent[key] = value
    else:
        setattr(parent, key, value)


def _get_at(parent: Any, key: str) -> Any:
    return parent[key] if isinstance(parent, dict) else getattr(parent, key)


def _apply_knobs(priors: Priors, params: dict[str, float]) -> None:
    for path, val in params.items():
        parts = path.split(".")
        parent = _walk_to_parent(priors, parts[:-1])
        last = parts[-1]
        existing = _get_at(parent, last)
        # int-typed knobs (max_attempts, lines_planned_mean) get rounded.
        # bool is a subclass of int — exclude.
        if isinstance(existing, int) and not isinstance(existing, bool):
            val = int(round(val))
        _set_at(parent, last, val)


# --- runner ---


def _extract_metrics(scenario: Scenario, result: Any) -> dict[str, float]:
    events = list(result.trace.events())
    priors = scenario.priors if scenario.priors is not None else load_default_priors()
    merged_clocks = [e.clock for e in events if e.kind == "MERGED"]
    # Total agent-minutes = Σ (cost / cost_rate_per_min) per ledger row.
    # This captures real *work* time across all agents, separate from
    # wall-clock cycle time.
    total_agent_min = 0.0
    for row in result.world.ledger_rows():
        rate = priors.agents.get(
            row.agent, priors.agents["developer"]
        ).cost_rate_per_min
        if rate > 0:
            total_agent_min += row.compute_cost_usd / rate
    return {
        "total_billed_usd": result.world.total_billed_usd(),
        "n_escalated": float(sum(1 for e in events if e.kind == "ESCALATED")),
        "n_merged": float(sum(1 for e in events if e.kind == "MERGED")),
        "n_review_completed": float(
            sum(1 for e in events if e.kind == "REVIEW_COMPLETED")
        ),
        "cycle_time_min": float(result.clock.now),
        "last_merge_clock_min": (
            float(max(merged_clocks)) if merged_clocks else 0.0
        ),
        "total_agent_minutes": total_agent_min,
        "budget_exceeded": float(any(e.kind == "BUDGET_EXCEEDED" for e in events)),
        "ledger_rows": float(len(list(result.world.ledger_rows()))),
    }


def _one_run(
    scenario_factory: Callable[[], Scenario],
    params: dict[str, float],
    seed: int,
) -> RunRecord:
    scenario = scenario_factory()
    base = scenario.priors if scenario.priors is not None else load_default_priors()
    priors = base.model_copy(deep=True)
    _apply_knobs(priors, params)
    scenario.priors = priors

    result = run_scenario(scenario, seed=seed, priors=priors)
    return RunRecord(
        scenario=scenario.name,
        seed=seed,
        params=dict(params),
        metrics=_extract_metrics(scenario, result),
    )


def _build_sampler(d: int, kind: str, seed: int) -> qmc.QMCEngine:
    if kind == "sobol":
        return qmc.Sobol(d=d, scramble=True, seed=seed)
    if kind == "lhs":
        return qmc.LatinHypercube(d=d, seed=seed)
    raise ValueError(f"unknown sampler {kind!r}")


def run_sweep(
    scenario_factory: Callable[[], Scenario],
    sweep: ParameterSweep,
    n_jobs: int = -1,
) -> list[RunRecord]:
    """Execute the full M·K-run sweep, parallelised.

    `n_jobs=-1` uses all cores; `n_jobs=1` runs serially (use for
    debugging — pdb across joblib workers is a pain).
    """
    knob_names = list(sweep.knobs)
    lo = [sweep.knobs[k][0] for k in knob_names]
    hi = [sweep.knobs[k][1] for k in knob_names]

    sampler = _build_sampler(len(knob_names), sweep.sampler, sweep.sampler_seed)
    raw = sampler.random(n=sweep.points)
    points = qmc.scale(raw, lo, hi)

    jobs: list[tuple[dict[str, float], int]] = [
        (dict(zip(knob_names, point.tolist(), strict=True)), seed)
        for point in points
        for seed in range(sweep.seeds_per_point)
    ]

    return list(
        Parallel(n_jobs=n_jobs, prefer="processes")(
            delayed(_one_run)(scenario_factory, params, seed) for params, seed in jobs
        )
    )


# --- output ---


def records_to_csv(records: list[RunRecord], path: Path) -> None:
    """Flatten records to one CSV row per run. Columns: scenario, seed,
    each knob, each metric.
    """
    if not records:
        path.write_text("")
        return
    knob_cols = sorted(records[0].params)
    metric_cols = sorted(records[0].metrics)
    header = ["scenario", "seed", *knob_cols, *metric_cols]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        for r in records:
            w.writerow(
                [r.scenario, r.seed]
                + [r.params[k] for k in knob_cols]
                + [r.metrics[m] for m in metric_cols]
            )
