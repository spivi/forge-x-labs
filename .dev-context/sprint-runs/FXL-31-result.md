# FXL-31 — Per-family Terraform emitter (graph-driven)

**Status**: SUCCESS
**PR**: #34 — https://github.com/spivi/forge-x-labs/pull/34
**Branch**: `fix/FXL-31-per-family-emitter`
**Files changed**: 6 (5 modified/added source, 1 test)
**Tests added**: 9 net-new emitter tests (10 total in `test_terraform_emitter.py`, was 4)

## What changed

- `TerraformEmitter` now takes the `ScenarioGraph` and renders `iam.tf` / `s3.tf` /
  `network.tf` from the graph nodes' `type` + `attributes`; `providers.tf` /
  `variables.tf` / `main.tf` stay static.
- New `app/cloudforge/pipeline/terraform_resource_blocks.py` holds per-resource block
  builders (role / policy / bucket + compensating-control policy / vpc / subnet / sg),
  keeping every module <200 lines and every function <30 lines.
- `terraform_blocks.py` reduced to the static builders + per-file assemblers that map
  the node list through the resource builders. A file with no matching node type emits
  an empty-but-valid header (`terraform validate` still passes).
- `artifacts.py` passes `bundle.graph` into the emitter.
- Subnet/SG blocks are wired to the family's VPC (`vpc_id`) so `terraform validate`
  passes (fixed a genuine "aws_subnet requires vpc_id" error found during e2e).
- Added constants `DEFAULT_INGRESS_PORT`, `EMPTY_TF_HEADER` (no magic literals).

## Acceptance criteria

- [x] `ci_cd_iam_chain` regression: DeployRole, RuntimeRole, iam:PassRole policy,
      broad-S3-read (s3:Get*/List*) policy, customer-exports + public-assets buckets
      (public-assets gets the compensating-control bucket policy), VPC/subnet/0.0.0.0/0 SG.
- [x] `public_data_exposure` emits ITS resources (customer-pii + public-looking-backups
      buckets, prod VPC) and NO ci_cd PassRole chain (`iam.tf` is the empty header).
- [x] `terraform validate` PASSES for both families; checkov/opa WARN (fail-soft, not installed).
- [x] Test asserts pde `s3.tf` names its public bucket and pde `iam.tf` has no `iam:PassRole`.
- [x] ci_cd HCL regression test (key resources present, no forbidden actions).
- [x] ruff + mypy --strict clean; coverage on app 96.15% (>=80%).

## Validation

- **ruff**: clean (`ruff check app/ tests/cloudforge/` + `ruff format`)
- **mypy --strict app/**: Success, no issues (35 files)
- **pytest + coverage**: 69 passed; total coverage 96.15% (new emitter modules at 100%)
- **CLI e2e (both families)**: `generate` + `validate` run against
  `examples/ci_cd_iam_chain.yaml` and `examples/public_data_exposure.yaml`; both show
  `[PASS] terraform validate`. Confirmed `out/pde/terraform/` describes the public-exposure
  resources (customer-pii bucket, prod VPC) and NOT the ci_cd IAM chain.
- **CI (PR #34)**: lint-and-type-check ×2 SUCCESS, test ×2 SUCCESS; PR MERGEABLE. Not merged.

## Notes / gotchas

- The installed `cloudforge` console script resolved to the parent repo's `.venv`
  (`/Users/.../forge-x-labs/.venv/bin/cloudforge`) and ran a STALE installed `app`
  package, masking the fix during e2e. Ran the CLI as
  `PYTHONPATH=. .venv/bin/python -m app.cli ...` to exercise the worktree source.
  Recommend the worktree's `.venv` install `app` editable (or always invoke via
  `-m app.cli`) for future e2e runs.

## Blockers

None.
