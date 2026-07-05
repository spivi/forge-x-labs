# Project Management — Forge X Labs (`cloudforge`)

Project management lives on **GitHub Issues + a GitHub Project board**. This directory
mirrors that state locally so there is a record in-repo and exact commands to reproduce
it.

- **Repo:** [spivi/forge-x-labs](https://github.com/spivi/forge-x-labs) (private)
- **Project board:** [Forge X Labs (cloudforge) — project #6](https://github.com/users/spivi/projects/6)
- **Milestones:** [M0–M6](https://github.com/spivi/forge-x-labs/milestones)

## Milestones

| # | Milestone | Focus |
|---|-----------|-------|
| M0 | Template adaptation and project skeleton | Adapt template, identity, `app/cloudforge` layout, CI green |
| M1 | Scenario graph and first generator | Graph/scenario schema, `ci_cd_iam_chain` generator, ground truth |
| M2 | Terraform emitter | Valid-for-static-analysis Terraform mapped from the graph |
| M3 | Local validators | Fail-soft schema/terraform/checkov/OPA + stdlib graph-risk engine |
| M4 | Reporting | `report.md` with ground truth, findings, remediation, banner |
| M5 | Mutation engine | `MutationGenerator` variants (**deferred** — not in MVP) |
| M6 | Documentation and wiki | README, wiki pages, roadmap, safety, template feedback |

## Issues

Status as of the MVP vertical-slice delivery (commit `ada60c1`).

| # | Issue | Milestone | Status |
|---|-------|-----------|--------|
| 1 | Inspect and adapt agentic repo template | M0 | ✅ done |
| 2 | Define architecture + source-of-truth hierarchy | M0 | ✅ done |
| 3 | Add or adapt CLI skeleton | M0 | ✅ done |
| 4 | Define scenario YAML schema | M1 | ✅ done |
| 5 | Define graph JSON schema | M1 | ✅ done |
| 6 | Implement `ci_cd_iam_chain` template generator | M1 | ✅ done |
| 7 | Implement graph path validator | M3 | ✅ done |
| 8 | Implement Terraform emitter (IAM/S3/SG) | M2 | ✅ done |
| 9 | Generate expected findings | M1 | ✅ done |
| 10 | Generate ground-truth paths | M1 | ✅ done |
| 11 | Add Checkov integration (fail-soft) | M3 | ✅ done |
| 12 | Add OPA/Rego policy and integration | M3 | ✅ done |
| 13 | Add report generator | M4 | ✅ done |
| 14 | Add mutation engine | M5 | ⏸️ deferred |
| 15 | Add tests | M3 | ✅ done |
| 16 | Add README quickstart | M6 | 🟡 in this slice |
| 17 | Create Wiki Home page | M6 | 🟡 staged in `docs/wiki/` |
| 18 | Wiki: Architecture | M6 | 🟡 staged in `docs/wiki/` |
| 19 | Wiki: Scenario Schema | M6 | 🟡 staged in `docs/wiki/` |
| 20 | Wiki: Graph Model | M6 | 🟡 staged in `docs/wiki/` |
| 21 | Wiki: Validation Pipeline | M6 | 🟡 staged in `docs/wiki/` |
| 22 | Wiki: Roadmap + Modal/diffusion | M6 | 🟡 staged in `docs/wiki/` |
| 23 | Document template feedback for owner | M6 | 🟡 staged in `docs/wiki/` |

## Reproduce the board from scratch

If you need to recreate this on a fresh clone:

```bash
# Milestones (one per M0–M6)
gh api -X POST repos/spivi/forge-x-labs/milestones -f title="M0 - ..." -f description="..."

# Issues (title/body/milestone-title)
gh issue create --repo spivi/forge-x-labs --title "..." --body "..." --milestone "M0 - ..."

# Project board + add issues
gh project create --owner spivi --title "Forge X Labs (cloudforge)"
gh project item-add <PROJECT_NUMBER> --owner spivi \
  --url https://github.com/spivi/forge-x-labs/issues/<N>
```

The full generator script is preserved as this session's `create_issues.sh` (scratchpad).
