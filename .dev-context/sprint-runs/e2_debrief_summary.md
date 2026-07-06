# FXL-E2 Learning-Corpus Epic — Debrief Summary

**Date:** 2026-07-06
**Scope:** cloudforge FXL-E2 "Cloud Risk Pattern Learning Corpus" epic — the three build tickets #98 (real seed fragments), #71 (training export gate), #73 (`cloudforge learn` CLI), all merged to master (`af475aa`). Each passed a fresh-context Opus review gate before merge.

## What shipped

| Ticket | Type | Effort | Est. model | Actual model | Est. min | Actual sec | Actual min | PR | Review gate |
|--------|------|--------|-----------|--------------|----------|-----------|-----------|-----|-------------|
| FXL-98 | feature | L | opus | **fable** | 46 | 4262 | ~71 | #99 | Opus APPROVE (executed pipeline) |
| FXL-71 | feature | M | sonnet | sonnet | 46 | 938 | ~16 | #100 | Opus APPROVE (24 gov-boundary probes) |
| FXL-73 | feature | M | sonnet | sonnet | 46 | 1131 | ~19 | #101 | Opus APPROVE (all 8 checks executed) |

All three delivered **green on first CI run (0 fix cycles)**, `ruff` (0.9.4) + `mypy --strict` clean, integrating master at **457 tests / ~98% coverage** on the learn package. The full `cloudforge learn` pipeline was verified end-to-end via the real CLI (ingest 14 → validate-corpus PASS → summarize → export-training).

## The headline outcome: real, honestly-gated corpus

`cloudforge learn export-training` produces an **honest 12/14** training bundle. The 2 excluded seeds (`s3-missing-access-logging-aws-001`, `cloudtrail-logging-missing-aws-008`) are genuinely-simple absence-of-logging risks whose fragments are legitimately edge-less and score below the 0.70 quality bar — excluded via `below_quality_bar`, **not gamed**. Both the author's tests and the review gate recomputed this live against the real catalog.

## The pivotal lesson (why this epic mattered)

An earlier attempt (#96) auto-built graph fragments that **passed all mechanical validation** (`validate_fragment`: endpoints resolve, known node types, quality score ≥ bar) while encoding **semantically FALSE** cloud relationships — `IAMPolicy -can_read-> IAMRole` (a policy is a document attached to an identity, never an actor), and a fabricated `DataSet` node forced into an IAM scenario with no data. Structure-only validation could not catch it; only an **adversarial meaning review** did.

FXL-98 fixed it by hand-authoring 14 real fragments (using Fable for careful semantic authoring) plus tests that assert the exact false shapes are **absent** (no `IAMPolicy` edge actor; `DataSet` only in real data-sink seeds; `kms_key → IAMPolicy` via its key policy, never silently `Application`). The review gate for each ticket then **executed** the pipeline to independently confirm the claims rather than trusting the author's report.

**Takeaway for the council:** for any artifact whose value IS its correctness (a training/benchmark corpus), the review gate must judge semantics, not just structure — and the reviewer must run the pipeline to recompute claimed counts. This is now recorded in `patterns.md`.

## Governance boundary (FXL-71)

The export gate reuses `RiskPattern.training_eligible` (a computed_field encoding validation + safety + reuse + FXL-D007) as the single source of truth, and adds only the 0.70 quality bar + an opt-in `--include-restricted` relaxation. The absolute exclusion (`unsafe_operational`) is checked **first**, before any relaxation branch, so it cannot be bypassed. The Opus gate ran 24 adversarial probes (including the ordering attack: unsafe + restricted + flag + quality 0.99 → correctly rejected). No leaks.

## Learning-loop outcome

- **Quantitative calibration:** `debrief.py` analyzed **23 runs** (E2 actuals backfilled into the ledger, since the build agents were dispatched directly rather than via `/sprint execute`, so the SessionEnd/SUBAGENT_LEDGER_CAPTURE hooks did not auto-record them). All call-to-action items were **[TUNE]** (auto-applied); **zero [CREATE]** items requiring a structural decision.
  - `type:feature` factor **0.383** (15 runs, CI 0.279–0.487) — the estimator over-predicts wall-clock by ~2.6×.
  - `label:effort:M` **0.383** (19 runs); `label:area:corpus` **0.41** (12 runs, CI 0.25–0.606).
  - Model policy: everything is `sonnet`-sufficient or lower (**0 underpowered** in any bucket); `label:area:corpus` is **10 well-matched / 2 overkill over 12 runs** on sonnet — the corpus tickets were well-routed. `label:effort:S` and `label:area:generation` flagged as down-tierable (haiku / sonnet).
- **Simulator (loop B):** `lemmings fit` fitted **2 knobs** — `agents.developer.cost_rate_per_min = 0.1095` and `bugs.base_lambda = 0.0`. The **zero bug lambda** reflects that the E2 wave shipped with no post-review defects: every ticket passed its fresh-context review gate on the first cycle. Skipped knobs (too few samples): code_reviewer cost rate (3 < 5), review duration (0 < 5), per-line violations (no data).
- **Backlog re-seed:** `tracker.py refresh` re-derived labels; the only tracked tickets are the just-closed E2 trio (no open backlog to re-seed).

## Known follow-ups

**Out of scope for THIS epic (single-source, local seed catalog), but blockers for the NEXT one (adding a second real source):**

- **#90 (blocker for a 2nd source)** — checkov adapter live-parse: the real policy-index page has an extra leading column, so the adapter extracts 0 records from a live fetch (the recorded fixture works). The FXL-E2 epic ships complete on the local `rule_catalog_yaml` source alone, so this does not block E2 — but it **must** be fixed before any live networked second source (e.g. csa-ccm mappings) can be ingested. Promote to a tracked blocker on the second-source milestone.

**Low priority, non-blocking:**

- **#79** — OPA critical-chain check is existence-only, not connectivity (defense-in-depth hardening).
- **Fable pricing gap:** `claude-fable-5` isn't in `budgets.yml` pricing, so #98's build cost logged as $0 (duration captured correctly, which is what estimate calibration needs). Worth adding a Fable pricing family. Note: any *cost* conclusions involving #98 are therefore incomplete; the model-routing conclusions (which use duration + suitability, not dollar cost) are unaffected.

## Evidence appendix (verifiable handles)

Maps the strongest claims to artifacts a reader can independently check:

| Claim | Where to verify |
|-------|-----------------|
| Merges + PRs | master merge commits `24bf881` (#98), `4ea0f7d` (#71), `af475aa` (#73); PRs #99/#100/#101 on `spivi/forge-x-labs` |
| Each passed a fresh-context Opus review gate | `ai-code-review` commit status = `success` on each PR head SHA (`e8d0aab`, `31bad98`, `6cac780`); verdicts recorded in `.dev-context/kpis/reviews.csv` (provider `claude-opus`); PR comments posted by `debrief.py --post-review-audit` |
| Honest 12/14 export, "not gamed" | reproduce: `PYTHONPATH=. .venv/bin/python -m app.cli learn ingest --adapter rule_catalog_yaml --corpus <c> && ... export-training --corpus <c> --out <o>` → `manifest.json` shows `exported_count:12, excluded_count:2, excluded_breakdown.below_quality_bar:2` (else 0); the 2 excluded seeds score 0.673 / 0.648 (< 0.70 bar); asserted in `tests/cloudforge/learn/test_seed_fragments.py::TestHonestExportability` + `test_export.py` |
| #96 false-semantics narrative | the #96 fabrication + its removal is on master history (`8bc3bee` fix + PR #97); the absent-false-shape invariants are locked in `tests/cloudforge/learn/test_seed_fragments.py::TestFragmentSemantics` (`test_no_policy_node_is_ever_an_edge_actor`, `test_dataset_nodes_appear_only_where_data_exposure_is_inherent`, `test_kms_seed_models_the_key_via_its_key_policy_not_application`) |
| Governance "no leaks" (unsafe/restricted can't bypass) | gate logic `app/cloudforge/learn/export.py:64` (unsafe checked first); asserted in `tests/cloudforge/learn/test_export.py` (unsafe+flag, metadata_only+flag, exact-bar boundary) |
| 23-run calibration metrics | `python scripts/debrief.py --dry-run` over `.dev-context/cost-ledger.csv` + `.dev-context/kpis/estimates.csv`; factors written to `.dev-context/kpis/calibration.json`; call-to-action appended to `.dev-context/kpis/recommendations.md`. "underpowered/well-matched/overkill" are defined in `scripts/debrief.py::_suitability`. E2 actuals are the 6 rows in `cost-ledger.csv` for FXL-98/71/73 (developer + code_reviewer). |
| "green on first CI run" scope | the required GitHub checks `lint-and-type-check` + `test` (`.github/workflows/ci.yml`); conclusion `SUCCESS` on each PR head SHA (`gh pr view <PR> --json statusCheckRollup`). Does not include the Opus review gate, which is a separate in-session status. |
| lemmings fit (2 knobs, bug λ=0) | `PYTHONPATH=lemmings/src .venv/bin/python -m lemmings.cli fit` → `.dev-context/sim/priors.override.yml` |
