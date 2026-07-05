# Planning Gate

> **HARD STOP.** Implementation work runs only on tickets that have been planned:
> estimated and model-routed. This is what makes the closed learning loop work —
> every run is measured against a prediction.

## The rule

Before `/develop` (or any agent) starts coding a ticket, it MUST pass the gate:

```bash
python scripts/tracker.py ready <TICKET>   # exit 0 = launchable, exit 1 = blocked
```

A ticket is **launchable** iff its row in `.dev-context/kpis/estimates.csv` has:
1. a non-empty `estimate_minutes` (AI wall-clock prediction), and
2. a non-empty `recommended_model` (cheapest-sufficient model), and
3. a launchable `status` (`planned`, `ready`, or `in_progress`).

If the gate fails, **do not code**. Tell the human to plan the ticket first:

```bash
python scripts/tracker.py plan <TICKET> --type <feature|fix|tweak|...> --labels "effort:M;..."
# or run /prd, which stamps estimate + model on every minted ticket
```

## Why estimate + model are mandatory

- **Estimate** (`estimate_minutes`): the planning-time prediction the `/debrief`
  loop calibrates against real session `duration_sec`. No estimate → no learning.
- **Model** (`recommended_model`): the cheapest model expected to deliver
  (`haiku` < `sonnet` < `opus`), seeded by `.dev-context/planning/base-estimates.yml`
  and tuned by `kpis/model-policy.json`. Routing never drops below the effort floor.

Both are produced by `scripts/estimator.py` (heuristic seed × learned factors) and
stored canonically in `estimates.csv`. The tracker backend (`TRACKER_BACKEND` in
`project.conf`: `none` | `linear` | `github_projects`) only mirrors them outward —
the gate and the loop work with `none`.

## On start of work

When a launchable ticket actually starts, record it:

```bash
python scripts/tracker.py status set <TICKET> in_progress
```

so the run is attributed and `duration_sec` from the session ledger joins back to it.
