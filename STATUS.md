# Project Status

**Current Phase:** Sprint wave 1 delivered + debriefed (MVP + 2 features)
**Last Updated:** 2026-07-05

> **Debrief (2026-07-05):** 2 runs analyzed; calibration withheld (2 < min 3 samples — no
> over-fit). lemmings fitted `agents.developer.cost_rate_per_min=0.0139`. Council review of the
> debrief summary surfaced the per-family Terraform emitter defect → filed as **FXL-31** (#31, M2).

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
1. `/debrief` — the wave has real actuals (durations/tokens) to calibrate estimates + model routing.
2. More scenario families (cross-account trust, KMS key-policy, public snapshot) as new tickets.
3. Parameterize the Terraform emitter per-family (currently emits the ci_cd resource set for all families).
4. Wire checkov/OPA into CI once runners have the tools.

## Active Worktrees

| Branch | Worktree Dir | Ticket | Agent | Status | Files Touched |
|--------|-------------|--------|-------|--------|---------------|
| (none) | — | — | — | — | — |

## Active Tasks
- **M0–M5 complete** (template, graph+generator, terraform, validators, reporting, mutation engine).
- **M1 extended** — second scenario family delivered (`public_data_exposure`).
- **M6 (docs/wiki)** — README + wiki published.
- Backlog: additional families; per-family Terraform emitter; checkov/OPA in CI.

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
