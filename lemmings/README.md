# Lemmings

Stochastic discrete-event simulator for the agentic development pipeline.

The 8-agent pipeline (Scrum Master, Developer, Code Reviewer, Security
Architect, Budget Review, E2E Tester, PM, Handoff Manager) coordinated by
skills (`/sprint`, `/develop`, `/hotfix`, `/release`) is expensive to
exercise — every dry-run burns LLM tokens. Lemmings models it well enough
to validate orchestration without spending tokens.

## Architecture

- **Decision core** (`lemmings.core.*`) — pure Python extracted from the
  markdown skills. Single source of truth.
- **World** — Protocol with `SimWorld` (in-memory) and (future) `RealWorld`
  (gh + git + filesystem) implementations.
- **Agents** — Protocol with `sim/` (sample outcomes from priors) and
  (future) `real/` (invoke real subagent) implementations.
- **DES engine** — heap-based event loop, time in minutes.
- **SEM** — latent factor stochastic model: ticket / agent / process
  latents drive observable outcomes.

## v1 Scope

Bounded to validate orchestration correctness end-to-end:

- 4 sim agents: ScrumMaster, Developer, CodeReviewer, BudgetReview
- 5 decision-core modules: `budget_gate`, `select_ticket`, `merge_order`,
  `retry_loop`, `escalation`
- 5 of 11 correlations in the SEM (#1, #2, #4, #6, #10)
- 3 canned scenarios: `budget_exhausted`, `review_loop`,
  `merge_order_conflict`
- 5 invariants asserted via pytest

## Install

```bash
pip install -e dev-template/lemmings
```

## Smoke Test

```bash
lemmings level budget_exhausted --seed 42 --trace /tmp/trace.jsonl
pytest dev-template/lemmings/tests/scenarios/ -v
```

## Mode Switch

```bash
LEMMINGS_MODE=sim   # default — RV-driven sim agents
LEMMINGS_MODE=real  # (v2) invoke real subagents — burns tokens
```

## Monte Carlo Sweeps (optional `mc` extra)

Quasi-random parameter sweeps via `scipy.stats.qmc` (LHS / Sobol),
parallelised with `joblib`. Each sweep runs M parameter points × K
seeds, then writes one CSV row per run.

```bash
pip install -e ./lemmings[mc]

lemmings sweep review_loop \
    --knob retry.max_attempts:1:5 \
    --knob budget.hard_cap_factor:1.0:2.0 \
    --points 32 --seeds 10 --sampler lhs \
    --out /tmp/sweep.csv -j -1
```

Knobs are dotted paths into `Priors` — anything from
`priors_default.yml` is fair game (e.g. `agents.code_reviewer.false_positive_rate`,
`bugs.base_lambda`, `review.violation_threshold`). Integer-typed knobs
(like `max_attempts`) are rounded.

Programmatic API:

```python
from lemmings.scenarios.review_loop import build
from lemmings.sim.montecarlo import ParameterSweep, run_sweep, records_to_csv

sweep = ParameterSweep(
    name="retry_cap_vs_cost",
    knobs={"retry.max_attempts": (1, 5), "budget.hard_cap_factor": (1.0, 2.0)},
    points=32, seeds_per_point=10,
)
records = run_sweep(build, sweep)
records_to_csv(records, Path("/tmp/sweep.csv"))
```

Each record carries `total_billed_usd`, `n_escalated`, `n_merged`,
`n_review_completed`, `cycle_time_min`, `budget_exceeded`, `ledger_rows`.
