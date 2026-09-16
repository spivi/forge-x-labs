# Validation Pipeline

`cloudforge validate <dir>` runs a **fail-soft** sequence
(`app/cloudforge/validate/orchestrator.py`). A missing optional tool produces
a `WARN` and is skipped. Only a real check failure produces a `FAIL`.

## Steps (in order)

1. **scenario schema**: re-validate `scenario.yaml` against `ScenarioSpec`.
2. **graph schema**: re-validate `graph.json` against `ScenarioGraph`.
3. **terraform**: if `terraform` is on `PATH`, `terraform init -backend=false`
   then `terraform validate`. Network/provider-download problems become
   `WARN`. Genuine syntax/config errors become `FAIL`.
4. **checkov**: if `checkov` is on `PATH`, scan `terraform/`, write
   `scanner_results/checkov.json`. Absent becomes `WARN`.
5. **opa**: if `opa` is on `PATH`, `opa eval` `policies/scenario.rego` over
   `graph.json`. Any `deny` is `FAIL`. Absent becomes `WARN`.
6. **graph-risk engine**: always runs (stdlib only).

## Graph-risk engine

| Check | FAIL condition |
|-------|----------------|
| ground-truth nodes exist | a path names a node absent from the graph |
| ground-truth edges exist | a path names an edge (`from->type->to`) absent from the graph |
| ground-truth path exists | consecutive path nodes are not connected by a real edge |
| scenario constraints | node count exceeds `max_resources`, or too few critical paths |
| no forbidden permissions | an `IAMPolicy` grants a destructive action |
| broad grants documented | a broad `s3:Get*`/`s3:List*` grant has no matching expected finding |

Forbidden-permission checks run on graph/policy `actions` attributes. HCL
string scanning exists in tests as secondary defense.

## Exit policy

`validate` prints one line per outcome and exits **nonzero only if any
outcome is `FAIL`**. Missing optional tools (`WARN`) never change the exit
code.

```
[PASS] terraform validate.
[WARN] checkov scan. not found, skipping
[FAIL] no forbidden permissions. pol-danger grants iam:DeleteRole (matches iam:Delete*)
```
