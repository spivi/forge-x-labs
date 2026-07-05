---
name: debrief
description: "Closed-loop calibration: compare planning estimates against measured actuals, learn estimate factors + cheapest-sufficient model routing, fit the lemmings simulator priors, and emit a prioritized call-to-action. Use when: /debrief, calibrate estimates, post-sprint retro, tune model routing, why are estimates off, learning loop, update priors. Runs after a sprint or batch of merged tickets."
---

# Debrief Skill

Close the learning loop: turn real outcomes into sharper estimates, cheaper-but-
sufficient model routing, and calibrated simulator priors.

## When to run

After a sprint, or after a batch of tickets reaches `done`. Needs accrued data
in `.dev-context/cost-ledger.csv` (with `duration_sec`) and
`.dev-context/kpis/estimates.csv`. Cold start (little data) is safe — it no-ops.

## Steps

1. **Preview** — run the engine dry first and read the report:
   ```bash
   python scripts/debrief.py --dry-run
   ```
   It prints accuracy tables (calibration factors with 95% CI), the
   cheapest-sufficient model policy, and a P1/P2/P3 call-to-action.

2. **Apply (quantitative loop)** — commit the learned factors:
   ```bash
   python scripts/debrief.py
   ```
   Writes `kpis/calibration.json` + `kpis/model-policy.json` and appends to
   `kpis/recommendations.md`. These are auto-applied: the next `/prd` estimate
   and model routing read them via `scripts/estimator.py`.

3. **Re-seed the backlog** — push learned factors onto not-yet-started tickets:
   ```bash
   python scripts/tracker.py refresh-labels   # alias: tracker.py refresh
   ```
   Idempotent (re-derives from the immutable seed × current factors).

4. **Fit the simulator (loop B)** — calibrate lemmings priors from real KPIs:
   ```bash
   PYTHONPATH=lemmings/src python -m lemmings.cli fit
   ```
   Writes `.dev-context/sim/priors.override.yml` for knobs with enough samples
   (cost rates, bug lambda, review duration); reports what was skipped. Then
   optionally sweep under the fitted priors to find better knob settings and
   surface agent/skill/rule edit recommendations (see
   [[lemmings_knob_to_file_map]] for which file each knob maps to):
   ```bash
   PYTHONPATH=lemmings/src python -m lemmings.cli sweep <scenario> --knob <path:lo:hi> --out /tmp/sweep.csv
   ```

5. **Triage the call-to-action (HITL)**:
   - **[TUNE]** recs are already auto-applied (calibration / model-policy). Note them.
   - **[CREATE]** recs (new component, rule tightening) need a human decision —
     surface each via `AskUserQuestion`; file approved ones as gated follow-up
     tickets. **Never auto-apply a structural change.**

6. **Record** — add any durable lesson to `.claude/cc10x/patterns.md`, and update
   `STATUS.md` with the debrief date + headline factors.

## Guardrails

- Tickets marked `scope_changed` are excluded from calibration (partial work
  distorts the signal).
- Model routing never drops below the effort floor in
  `.dev-context/planning/base-estimates.yml`.
- A factor is only trusted with enough samples (`min_samples`, default 3).
