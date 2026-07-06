<!-- cc10x session memory: ACTIVE CONTEXT. DO NOT DELETE.
     What is being worked on RIGHT NOW. Read at session start; updated at session
     end (and by /handoff). Session-scoped: prune stale entries. For durable
     architecture decisions use .dev-context/DECISIONS.md instead; for recurring
     gotchas use patterns.md. -->

# Active Context

## Current Focus
- **FXL-E2 "Cloud Risk Pattern Learning Corpus" epic COMPLETE** (2026-07-06, master `af475aa`).
  `cloudforge learn` is a working CLI: fetch-sources / ingest / validate-corpus / summarize /
  export-training. The corpus has 14 hand-authored, semantically-REAL graph fragments; the
  export gate produces an HONEST 12/14 training bundle (2 excluded = genuinely-simple
  absence-of-logging seeds, below the 0.70 quality bar — not gamed).

## Recent Changes
- [2026-07-06] **#98** — authored 14 real, semantically-correct `graph_fragment`s in
  `data/rule_catalog/seed_patterns.yaml` (Fable), replacing the #96 heuristic fabrication.
  Adapter (`_embedded.py`) validates + JSON-encodes them into `raw_payload["graph"]`; the
  normalizer reuses them verbatim. Fresh-context Opus gate EXECUTED the pipeline to confirm.
- [2026-07-06] **#71** — training-export gate (`export.py`): reuses `training_eligible`
  (single source of truth, honors FXL-D007) + quality>=0.70; `--include-restricted` never
  admits `unsafe_operational` (checked first). Opus gate ran 24 governance-boundary probes.
- [2026-07-06] **#73** — `cloudforge learn` nested Typer group; pipeline logic untouched.
- [2026-07-06] Untracked an accidentally-committed `.venv` symlink (`ac559a4`).

## Next Steps
1. Low-priority follow-ups: **#90** (checkov live-parse: extra leading column → 0 records
   from real fetch), **#79** (OPA critical-chain existence-only, not connectivity).
2. `/debrief` to calibrate estimate factors + model routing from the E2 wave actuals.
3. Optional: 2nd/3rd real source adapter (csa-ccm mappings) once #90 is fixed.

## Decisions
- FXL-D001 (`app/cloudforge/` layout, zero CI edits) and FXL-D002 (deterministic generation
  first; validators + ground truth over cleverness) — promoted to DECISIONS.md.

## Learnings
- _(session-local insights; promote durable ones to patterns.md)_

## References
- _(links to plans, PRDs, tickets relevant to current work)_

## Blockers
- None

## Last Updated
_(date — one-line summary)_
