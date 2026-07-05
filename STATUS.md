# Project Status

**Current Phase:** Wave 1 + FXL-31 delivered; learning loop calibrated
**Last Updated:** 2026-07-05

> **Debrief (2026-07-05):** After FXL-31 (per-family Terraform emitter, PR #34, AI review gate
> APPROVE), the loop has **3 samples** and committed real factors: `label:effort:M` /
> `label:area:generation` estimate factor = **0.546** (CI 0.376–0.715); model policy → **sonnet**
> (3/3 overkill); lemmings `cost_rate_per_min` 0.0139 → 0.0208. **Proof it's live:** FXL-35
> (fix/M/generation) now estimates 25m/sonnet vs FXL-31's pre-cal 45m. PR-#34 review nits (per-family
> tags + HCL escaping) filed as **FXL-35** (#35, M2).

## Recent Achievements
- **MVP vertical slice** (PR #24): `generate → validate → report` end-to-end for the
  `ci_cd_iam_chain` family — models, TemplateGenerator, Terraform emitter, fail-soft
  validators + stdlib graph-risk engine, Markdown report, Typer CLI.
- **Sprint wave 1 (both merged):**
  - **FXL-26** (PR #29) — second scenario family `public_data_exposure` (direct
    data-exposure risk; new `FindingFamily.S3_PUBLIC_EXPOSURE`). Proves the generator
    seam is family-agnostic.
  - **FXL-14** (PR #28) — seeded, deterministic `MutationGenerator` (+ `--mutate-seed N`
    CLI option): cosmetic/benign variants that preserve ground-truth risk. Same seed →
    byte-identical graph; risk engine PASS on all variants.
- Integrated master verified: `ruff` + `mypy --strict` clean, **63 tests / 95.77%
  coverage**, both families + mutation exercised end-to-end via the real CLI.
- **Review gates both on:** `AI_REVIEW_GATE` (tactical, per-PR) + `COUNCIL_REVIEW`
  (director-level doc council; engine vendored + verified live).
- Docs live: README + 10 wiki pages published to the GitHub Wiki; project board #6 linked
  to the repo.

### Next Steps
1. **FXL-35** (#35, planned 25m/sonnet) — emitter hardening: per-family `common_tags` + HCL escaping (from PR #34 review nits).
2. More scenario families (cross-account trust, KMS key-policy, public snapshot) as new tickets.
3. Wire checkov/OPA into CI once runners have the tools.
4. Route the next generation ticket through full `/sprint execute` so `SUBAGENT_LEDGER_CAPTURE` records exact tokens (not backfilled).

## Active Worktrees

| Branch | Worktree Dir | Ticket | Agent | Status | Files Touched |
|---|---|---|---|---|---|
| (none) | — | — | — | — | — |

## Active Tasks
- **M0–M5 complete** (template, graph+generator, terraform, validators, reporting, mutation engine).
- **M1 extended** — second scenario family (`public_data_exposure`).
- **M2 complete** — per-family (graph-driven) Terraform emitter (FXL-31).
- **M6** — README + wiki published.
- Backlog: **FXL-35** (emitter hardening, planned); additional families; checkov/OPA in CI.

## Agent Pipeline Status

| Agent | Definition | Trigger | Status |
|-------|-----------|---------|--------|
| Scrum Master | `.dev-context/agents/scrum_master.md` | `/sprint` skill | Ready |
| Code Reviewer | `.dev-context/agents/code_reviewer.md` | GitHub Action on PR | Ready |
| Developer Worker | `.dev-context/agents/developer.md` | Spawned by Scrum Master | Ready |
| Budget Review | `.dev-context/agents/budget_review.md` | Manual `/cost` or Scrum Master pre-check | Ready |
| Security Architect | `.dev-context/agents/security_architect.md` | GitHub Action on PR | Ready |
| Product Manager | `.dev-context/agents/product_manager.md` | `/prd` skill | Ready |
| E2E Tester | `.dev-context/agents/e2e_tester.md` | GitHub Action on PR | Ready |
| Handoff Manager | `.dev-context/agents/handoff_manager.md` | `/release` skill | Ready |

## Known Issues
<!-- Track known issues and blockers here -->
