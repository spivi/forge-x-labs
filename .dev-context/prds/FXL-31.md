# FXL-31 — Per-family Terraform emitter

**Status**: Draft
**Priority**: P2
**Type**: fix
**Effort**: M (3–5 files)
**Milestone**: M2 — Terraform emitter
**Maps to**: GitHub issue #31
**Surfaced by**: wave-1 debrief council review (coherence blocker)

## Problem

`TerraformEmitter.emit(terraform_dir)` takes no graph — its block builders
(`build_iam_tf()`, `build_s3_tf()`, `build_network_tf()`, …) are zero-arg and hardcode the
`ci_cd_iam_chain` resources. `ScenarioArtifacts` calls `TerraformEmitter().emit(dir)` without
the graph, so **every family gets identical ci_cd HCL**. For `public_data_exposure` the graph
and ground-truth are family-correct, but the emitted `terraform/` describes the wrong
resources. `terraform validate` still passes (the HCL is valid), so the mismatch is silent.

## Goal

Make the emitter **graph-driven**: render Terraform resources FROM the scenario's graph nodes
(their `type` + `attributes`), so the compiled `terraform/` matches each family's actual
resources.

## Approach

- Change `TerraformEmitter` to take the `ScenarioGraph` (constructor or `emit(graph, dir)`),
  and `ScenarioArtifacts.write_all` to pass `bundle.graph`.
- Drive resource blocks from graph nodes:
  - `IAMRole`/`IAMPolicy` nodes → `iam.tf` (roles, policies with each node's `actions`/`resource`).
  - `S3Bucket` nodes → `s3.tf` (a bucket per node; bucket policy when a node marks a
    compensating control).
  - `VPC`/`Subnet`/`SecurityGroup` nodes → `network.tf` (SG ingress from each node's
    `ingress_cidr`).
  - `providers.tf`/`variables.tf`/`main.tf` stay static (provider config + fake account id).
- Keep functions ≤30 lines / modules ≤200: `terraform_blocks.py` builders become small
  pure functions taking the relevant node list (split into a helper module if it grows).
- A file with no matching nodes emits an empty-but-valid `.tf` (or is skipped) — decide and
  document; `terraform validate` must still pass.

## Non-Goals

- No new scenario family, no mutation changes, no new node/edge types.
- Not aiming for byte-perfect AWS realism — just family-faithful, statically-valid HCL that
  a scanner sees as the family's resources.

## Acceptance Criteria

- [ ] `ci_cd_iam_chain` emits the SAME logical resources as today (regression): DeployRole,
      RuntimeRole, PassRole policy, broad-S3-read policy, customer-exports + public-assets
      buckets, VPC/subnet/0.0.0.0/0 SG.
- [ ] `public_data_exposure` emits ITS resources — the public bucket(s) + sensitive data
      context, and does NOT emit the ci_cd IAM PassRole chain.
- [ ] `terraform validate` passes for BOTH families; checkov/opa still fail-soft.
- [ ] A test asserts the emitted HCL reflects the family (e.g. `public_data_exposure`'s
      `s3.tf` names its public bucket; its `iam.tf` has no `iam:PassRole`).
- [ ] `ci_cd_iam_chain` HCL regression test (key resources still present).
- [ ] `ruff` + `mypy --strict` clean; coverage on `app` ≥80%.

## Affected Files

- `app/cloudforge/pipeline/terraform_emitter.py` (graph-driven)
- `app/cloudforge/pipeline/terraform_blocks.py` (builders take node lists; maybe split)
- `app/cloudforge/pipeline/artifacts.py` (pass `bundle.graph`)
- `tests/cloudforge/test_terraform_emitter.py` (extend), maybe a new per-family test

## Threat Model (advisory)

Local offline generator; no external surface. Output-integrity only: emitted HCL must never
contain a forbidden destructive action (the graph-risk engine already rejects those on policy
nodes, and the emitter renders only what the graph declares), and must keep the dummy account
id / fake values (never real secrets). Making the emitter graph-driven actually *reduces* risk
(HCL can no longer drift from the graph). **Residual risk: low.**

## Dependencies

- Depends on the shipped emitter + both families (all merged). Independent of any open work.
