<!-- cc10x session memory: ACTIVE CONTEXT. DO NOT DELETE. -->

# Active Context

## Current Focus
- v1 lab generator complete. All 6 PRs merged (#143, #146, #147, #149, #151, #153).
- 5 scenario families live, tested, and validated.
- `lab`, `grade`, `lab-cohort`, `grade-cohort` fully working.
- Next: run final release checks, public tag / PyPI prep.

## Recent Changes
- [2026-09-16] VAR-1 large run: 2000/2000 pass, 77 shapes, gate exit 0.
- [2026-09-16] `app/cloudforge/lab/` — strip/pack/grade; 14 tests; PR #147.
- [2026-09-16] FXL-D010 (student pack must not leak the key) on the lab branch.

## Next Steps
1. Merge #143 then #146.
2. Merge #147.
3. `lab-cohort` / `grade-cohort`.
4. F0 emitter + cross_account / kms / snapshot families.
5. LICENSE + README.

## Blockers
- None

## Last Updated
2026-09-16 — Grok handoff: three PRs open; AGY should review/merge then continue cohort + families.
