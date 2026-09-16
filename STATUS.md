# Project Status

**Current Phase:** v1 OSS lab-generator — variation GO; `lab`/`grade` in review
**Last Updated:** 2026-09-16

## Current State

- **Project**: FXL (`cloudforge`)
- **Phase**: v1 open-source release as a **lab generator**
- **Active task**: FXL-152 OSS hygiene (PR **#153**). Also open: #143, #146, #147, #149, #151.
- **Blocked on**: nothing. Merge order: **#143 then #146**; **#147** is independent of those two (based on master).
- **Last agent**: Grok 4.6 (xAI)
- **Last platform**: grok
- **Timestamp**: 2026-09-16T22:00:00Z

## Resume here (Antigravity / any other agent)

Read in this order. Do not re-litigate the product decision (labs, not diffusion).

1. This block.
2. [`docs/superpowers/plans/2026-09-16-v1-oss-labs.md`](docs/superpowers/plans/2026-09-16-v1-oss-labs.md)
3. `.dev-context/DECISIONS.md` (D001–D008 bind; D009/D010 drafted in working tree / PRs)
4. `.claude/cc10x/activeContext.md` + `progress.md`

**Open PRs (do these first):**

| PR | Ticket | What | Base |
|---|---|---|---|
| https://github.com/spivi/forge-x-labs/pull/143 | FXL-VAR-1g | `--gate` + aws_ci/aws_large | master |
| https://github.com/spivi/forge-x-labs/pull/146 | FXL-VAR-1h | docs + **2000-scenario GO** | #143 branch |
| https://github.com/spivi/forge-x-labs/pull/147 | FXL-144/145 | `lab` / `grade` / cohort | master |
| https://github.com/spivi/forge-x-labs/pull/149 | FXL-148 | `cross_account_trust` family | master |
| https://github.com/spivi/forge-x-labs/pull/151 | FXL-150 | KMS key + public EBS snapshot families | master |
| https://github.com/spivi/forge-x-labs/pull/153 | FXL-152 | Apache-2.0, SECURITY.md, job-first README | master |

**Verified evidence (VAR-1h):** 2,000 scenarios, 0 FAIL, 77 shapes, path lengths [3,5,6,7], decoys 66.4%, controls 47.4%, `--gate` exit 0. Tools were absent on PATH. Report: `.dev-context/sprint-runs/FXL-VAR-1-result.md` on the 1h branch.

**Do next:**

1. Review/merge #143, then #146.
2. Review/merge #147 (`lab` / `grade`). Leak tests are load-bearing.
3. Merge family PRs (#149, #151) and OSS hygiene (#153).
4. Public repo + PyPI tag after those merges.

**How to run:** `PYTHONPATH=. .venv/bin/python -m app.cli …` (console-script shebang may be stale).

```bash
# on feat/FXL-144-lab-pack:
PYTHONPATH=. .venv/bin/python -m app.cli lab examples/ci_cd_iam_chain.yaml --seed 17 --out /tmp/alice
PYTHONPATH=. .venv/bin/python -m app.cli grade /tmp/alice --submission examples/labs/alice_guess.yaml
```

Composer ids are namespaced (`core0/…`); the sample guess YAML uses template ids — for composer labs, copy node ids from `student/estate.json`.

## Recent Changes (this session)

- v1 plan written: `docs/superpowers/plans/2026-09-16-v1-oss-labs.md` (main working tree)
- FXL-VAR-1g: `evaluate_gate` + `--gate` — PR #143
- FXL-VAR-1h: docs + large-run GO — PR #146
- FXL-144/145: `app/cloudforge/lab/` strip/pack/grade — PR #147, 14 tests passed

## Open Questions

1. Composer vs template node ids in the example guess file (document in Labs.md).
2. `lab-cohort` not yet implemented.
3. D009/D010 are on feature branches / main working tree, not yet on origin/master.

## Next Steps

1. Merge PR #143 then #146.
2. Merge PR #147.
3. Implement lab-cohort / grade-cohort.
4. New families + emitter (F0–F3).
5. LICENSE / SECURITY.md / README (Phase 5).

## Active Worktrees

None (all 6 feature branches merged into master; temporary worktrees removed).

## Active Tasks

- [x] All 6 PRs merged (#143, #146, #147, #149, #151, #153)
- [x] 5 scenario families live and verified in composer + template generators
- [x] `lab`, `grade`, `lab-cohort`, `grade-cohort` CLI commands and tests merged
- [x] Clean up git worktrees
- [ ] Run release validation across all 5 families
- [ ] Tag v1.0.0 (or v0.1.0) and prepare PyPI release

## Agent Pipeline Status

| Agent | Definition | Trigger | Status |
|-------|-----------|---------|--------|
| Scrum Master | `.dev-context/agents/scrum_master.md` | `/sprint` skill | Ready |
| Developer Worker | `.dev-context/agents/developer.md` | Spawned by Scrum Master | Ready |

## Known Issues

- `.venv/bin/cloudforge` shebang may point at a deleted worktree; use `python -m app.cli`.
- Wiki/README still call `learn` / MutationGenerator unshipped — Phase 5 docs.
- Example `alice_guess.yaml` node ids match the **template** family, not composer namespaces.

## Session Log

| Timestamp | Agent | Platform | Note |
|---|---|---|---|
| 2026-07-16 | Claude | claude | FXL-VAR-1f merged (PR #142) |
| 2026-09-16 | Grok 4.6 | grok | v1 labs plan; PRs #143 (1g), #146 (1h GO), #147 (lab+grade) |

---

## Historical (not current next-steps)

Master HEAD `9d4a5c6` = VAR-1f. MVP, two families, composer, learn CLI, STRESS GO, E2 corpus are on master.
