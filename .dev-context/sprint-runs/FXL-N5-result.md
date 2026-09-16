# FXL-N5 — Result

**Ticket**: FXL-N5 — Scenario quality rubric + human review pack (M7 · docs · P2)
**Issue**: #48 (Closes)
**Status**: DONE — PR open, CI green, NOT merged (as instructed)
**PR**: #55 — https://github.com/spivi/forge-x-labs/pull/55
**Branch**: `docs/FXL-N5-quality-rubric` (based on origin/master)
**Commit**: `51a3305` docs(FXL-N5): add scenario quality rubric + human review pack (signed-off + co-authored)

## Deliverables (all under docs/)

1. **`docs/review-rubric.md`** — the scoring rubric.
   - 3 reviewer roles, each scores independently: cloud-security engineer,
     CSPM/detection engineer, red-team/cloud-assessment.
   - Five 1–5 scales with concrete 1/3/5 anchors: realism, clarity, training
     usefulness, scanner-benchmark usefulness, ground-truth trust.
   - Blind-then-reveal protocol (ground truth hidden first, revealed after, then
     the coherence question).
   - The open questions from the review brief (real env? risk chain plausible?
     findings too toy-like? remediation order? benchmark a scanner? train an
     analyst? what's missing?).
   - Explicit <20-min-per-scenario budget + a suggested per-reviewer score line.

2. **`docs/review-pack-template.md`** — the per-scenario 1-page format.
   - Reviewer view (summary, resources, risk narrative, findings WITHOUT the
     ground-truth "why"/remediation) + reveal (critical path, expected findings +
     why, remediation order, decoy note, coherence check).
   - A source-map table showing which real artifact each field comes from.
   - Format rules that keep the sheet under 20 min / ~1 page.

3. **`docs/review-pack-sample/`** — 10 review sheets + README index, from REAL output.
   - Families: `ci_cd_iam_chain` (base + seeds 1–4) and `public_data_exposure`
     (base + seeds 1–4) = 2 families + 8 seeded mutations = 10 scenarios.
   - Each sheet's fields copied from that scenario's real `report.md` /
     `graph.json` / `ground_truth_paths.json` / `expected_findings.json`.
   - Sheets are 74–88 lines each (~1 page), ground-truth-hidden + reveal.

## Provenance — pack is from real generated artifacts

Generated with the shipped CLI + deterministic mutation engine (no code changes):
`python -m app.cli generate examples/<family>.yaml --out <dir> [--mutate-seed N]`
then `report <dir>`. A throwaway generation/extraction/assembly helper ran in the
scratchpad ONLY (not committed). Raw `out/` trees are gitignored; only the assembled
1-page sheets are committed. Verified programmatically: across all seeds of each
family the ground-truth critical-path node IDs **and** edges are byte-identical to
base; mutations only rename display labels + add one benign `subnet-benign-extra`
decoy node — the human-facing evidence for definition point #12 (mutation preserves
ground truth, FXL-D003).

## Acceptance criteria
- [x] Reviewer can score realism/clarity/usefulness/ground-truth confidence in
      <20 min (rubric anchors + scannable 1-page sheets).
- [x] Sample pack from real cloudforge output (10 scenarios, both families +
      mutations), ground-truth-hidden + reveal.
- [x] Rubric + template committed under docs/.

## Scope discipline
- Docs-only. No `app/`, tests, emitter, scorer, mutation, or families touched.
- Sanity check: `pytest tests/cloudforge/ -q --no-cov` → 103 passed.
- No throwaway .py committed (all helpers stayed in scratchpad).

## CI
All checks green (lint-and-type-check + test ×2 → SUCCESS). mergeStateStatus: CLEAN.
Docs-only so CI passed trivially, as expected.

## Blockers
None.
