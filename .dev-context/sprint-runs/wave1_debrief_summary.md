# Sprint Wave 1 — Debrief Summary

**Date:** 2026-07-05
**Scope:** cloudforge sprint wave 1 — FXL-14 (mutation engine) + FXL-26 (`public_data_exposure` family), both merged to master.

## What shipped

| Ticket | Type | Effort | Est. model | Est. min | Actual sec | Actual min | PR |
|--------|------|--------|-----------|----------|-----------|-----------|-----|
| FXL-14 | feature | M | sonnet | 120 | 659 | ~11 | #28 |
| FXL-26 | feature | M | sonnet | 120 | 531 | ~9 | #29 |

Both delivered green on first CI run (0 fix cycles), `ruff` + `mypy --strict` clean, integrated
master at **63 tests / 95.77% coverage**. The **graph + ground-truth** for both families and the
mutation engine were verified end-to-end via the real CLI (generate → validate all-PASS → report;
mutation determinism: same seed → byte-identical graph).

**Scope of verification — important:** the Terraform *emitter* is NOT yet family-aware — it emits
the `ci_cd_iam_chain` resource set for every family, so the compiled `terraform/` artifact is only
correct for `ci_cd_iam_chain`. `terraform validate` passes for `public_data_exposure`, but the HCL
does not match that family's graph. This is tracked as a follow-up (see below) and does not affect
the source-of-truth graph/ground-truth, which are family-correct.

## Learning-loop outcome

- **Quantitative calibration:** `debrief.py` analyzed **2 runs**. It correctly **withheld**
  calibration factors and model-policy changes because the single `type:feature / effort:M`
  bucket has 2 samples < the `min_samples=3` guardrail. No factors were committed — the loop
  refused to over-fit on two data points. `calibration.json` / `model-policy.json` unchanged.
- **Simulator (loop B):** `lemmings fit` fitted **1 knob** from real KPIs —
  `agents.developer.cost_rate_per_min = 0.0139` (from measured token-cost ÷ duration) — and
  wrote `.dev-context/sim/priors.override.yml`. Other knobs skipped (too few samples: bugs 2<5,
  reviews 0<5, no per-line violation data).
- **Backlog re-seed:** no not-started tickets existed at debrief time → no-op. **(Updated:** the
  council review then surfaced the per-family emitter defect, now filed as **FXL-31** / issue #31
  in milestone M2 — so the backlog is no longer empty.)

## Signal worth noting (not yet actionable)

The two features finished in **~9–11 min against a 120-min cold-start estimate** — roughly an
order of magnitude faster. This is a strong directional signal that the `base_minutes.feature`
seed (120) is too high for M-effort generation-family work in this codebase, **but it is not yet
safe to act on**: 2 samples is below the trust threshold, and both tickets were unusually clean
(hardcoded/deterministic generation mirroring an existing template, 0 review cycles). One more
comparable feature would cross `min_samples` and let the loop commit a factor.

Caveat on the actuals: the sub-agents ran as directly-spawned background Task agents rather than
through the full `/sprint execute` machinery, so their ledger rows were **backfilled** from the
Task completion results (real durations; token totals allocated to the output column as an
approximation). The durations are accurate; the token split is estimated.

## Evidence anchors

- **Green merges (master):** FXL-26 = PR #29 → merge commit `a1dd908`; FXL-14 = PR #28 → merge
  commit `51c857b`; wave close = PR #30 → `d2854b4`.
- **Coverage / tests:** `poetry run pytest tests/cloudforge/ --cov=app` on `d2854b4` → 63 passed,
  95.77% (reproduce locally).
- **Mutation-determinism claim:** `cloudforge generate examples/ci_cd_iam_chain.yaml --out A
  --mutate-seed 42` and again `--out B --mutate-seed 42`; `diff A/graph.json B/graph.json` is empty
  (byte-identical). `--mutate-seed 7` yields a different `graph.json` with the same ground-truth
  node ids.
- **Ledger rows fed to `debrief.py`** (`.dev-context/cost-ledger.csv`): session
  `ab6397047fddbac8d` (FXL-14, dur=659s, in=8000/out=85654, notional $6.5441) and
  `a9f0f7a82ec6517ad` (FXL-26, dur=531s, in=7000/out=77297, notional $5.9023). **Token split is a
  backfilled approximation** (Task-completion totals allocated to the output column); durations are
  exact.
- **Simulator knob `cost_rate_per_min = 0.0139`:** emitted by `lemmings fit` from the two ledger
  rows above. NOTE: this does **not** equal the naive `total_notional_cost / total_minutes`
  ($12.4464 / 19.83 min = 0.6275) — `lemmings fit` applies its own normalization (per-token /
  prior-weighted), so the raw figure is not hand-reproducible from the ledger alone. Treat `0.0139`
  as a tool-internal fit over 2 samples, not a directly-audited rate; it will firm up with more data.

## Recommended next actions

1. **Do NOT lower the feature estimate yet** — wait for a 3rd comparable feature ticket, then
   `/debrief` will commit a calibrated factor with a 95% CI.
2. **Route the next mechanical generation ticket through `/sprint execute`** (not a direct spawn)
   so `SUBAGENT_LEDGER_CAPTURE` records exact token usage, not a backfilled approximation.
3. **Consider a lighter model floor** for deterministic "mirror an existing family" work: both
   tickets succeeded cleanly and might have run on a cheaper tier — but confirm with the
   calibrated model-policy once samples accrue, not by hand.
4. **Per-family Terraform emitter** is the top code follow-up — now filed as **FXL-31** (issue #31,
   milestone M2): the emitter still emits the ci_cd resource set for every family (the
   graph/ground-truth are family-correct, the HCL is not).

## Council review

This summary was reviewed by the document-review council (`COUNCIL_REVIEW=on`): Codex
(correctness-falsifiability) + Antigravity (coherence-scope) members, Sonnet chair via the
Architectural Methodologist persona. It raised two blockers — (1) the "verified end-to-end" claim
contradicted the acknowledged HCL emitter defect and the defect was untracked; (2) key factual
claims lacked evidence anchors. **Both are resolved above:** the verification claim is scoped, the
emitter defect is filed as FXL-31, and an Evidence section was added (including an honest note that
the `0.0139` knob is not hand-reproducible from the ledger). Council verdict is advisory; recorded
in `.dev-context/kpis/council.csv`.
