# Validation Pipeline

`cloudforge validate <dir>` runs a **fail-soft** sequence
(`app/cloudforge/validate/orchestrator.py`). A missing optional tool produces a `WARN` and
is skipped; only a real check failure produces a `FAIL`.

## Steps (in order)

1. **scenario schema** — re-validate `scenario.yaml` against `ScenarioSpec`.
2. **graph schema** — re-validate `graph.json` against `ScenarioGraph`.
3. **terraform** — if `terraform` is on `PATH`: `terraform init -backend=false` then
   `terraform validate`. Network/provider-download problems → `WARN`; genuine
   syntax/config errors → `FAIL`.
4. **checkov** — if `checkov` is on `PATH`: scan `terraform/`, write
   `scanner_results/checkov.json`. Absent → `WARN`.
5. **opa** — if `opa` is on `PATH`: `opa eval` `policies/scenario.rego` over `graph.json`,
   write `opa_results.json`. Any `deny` → `FAIL`. Absent → `WARN`.
6. **graph-risk engine** — always runs (stdlib only).

## Graph-risk engine (`graph_risk.py`)

Six checks over the reconstructed bundle:

| Check | FAIL condition |
|-------|----------------|
| ground-truth nodes exist | a path names a node absent from the graph |
| ground-truth edges exist | a path names an edge (`from->type->to`) absent from the graph |
| ground-truth path exists | consecutive path nodes are not connected by a real edge |
| scenario constraints | node count exceeds `max_resources`, or too few critical paths |
| no forbidden permissions | an `IAMPolicy` node grants `iam:Delete*`, `s3:DeleteBucket`, `ec2:TerminateInstances`, `kms:ScheduleKeyDeletion`, or `organizations:*` |
| broad grants documented | a broad `s3:Get*`/`s3:List*` grant has no matching expected finding |

Forbidden-permission checks run **primarily on the graph/policy `actions` attributes**
(the graph is the source of truth); HCL string scanning exists in tests only as secondary
defense-in-depth.

## Exit policy

`validate` prints one line per outcome and exits **nonzero only if any outcome is `FAIL`**.
Missing optional tools (`WARN`) never change the exit code. Example:

```
[PASS] terraform validate.
[WARN] checkov scan. not found — skipping
[FAIL] no forbidden permissions. pol-danger grants iam:DeleteRole (matches iam:Delete*)
```
