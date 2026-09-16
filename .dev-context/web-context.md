# Web Session Context — FXL (cloudforge)
Last synced: 2026-09-16T05:25:06Z

## Your Role
You are an advisor for the FXL project. Read-only mode — focus on
code review, planning, Q&A, and architectural guidance.
Use conventional commits. Follow rules in .dev-context/rules/.

## Current Status
**Current Phase:** FXL-E2 learning-corpus epic complete; `cloudforge learn` working; loop re-calibrated
**Last Updated:** 2026-07-06

### Next Steps
1. **FXL-35** (#35, planned 25m/sonnet) — emitter hardening: per-family `common_tags` + HCL escaping (from PR #34 review nits).
2. More scenario families (cross-account trust, KMS key-policy, public snapshot) as new tickets.
3. Wire checkov/OPA into CI once runners have the tools.
4. Route the next generation ticket through full `/sprint execute` so `SUBAGENT_LEDGER_CAPTURE` records exact tokens (not backfilled).

## Active Decisions
## FXL-D004: Harden validation before adding a third scenario family
## FXL-D005: `jsonencode` policy documents are LIVE HCL, and astral chars need raw UTF-8
## FXL-D006: Duplicate resource labels are rejected pre-emission, scoped per resource TYPE
## FXL-D007: CSA CCM control-ID mappings are training-eligible; control text is not; CIS stays restricted
## FXL-D008: OPA coarse-grained, graph engine precise — defense-in-depth via BFS reachability

