# FXL-35 — Harden Terraform emitter: per-family tags + HCL escaping

**Status**: Draft
**Priority**: P2
**Type**: fix
**Effort**: M
**Milestone**: M2 — Terraform emitter
**Maps to**: GitHub issue #35
**Surfaced by**: AI review gate on PR #34 (two non-blocking nits)

## Problem

Two residual issues in the now-graph-driven emitter (FXL-31):

1. **`common_tags` are hardcoded to the ci_cd family.** `terraform_blocks.py::build_main_tf`
   emits `locals.common_tags` fixed to `env=staging`, `app=analytics-exporter`. For
   `public_data_exposure` the graph declares `env=prod` / `app=customer-data-lake`, so the
   compiled tags disagree with the graph — the residual cross-family mismatch FXL-31 aimed to
   remove.
2. **Latent HCL injection.** `name`, `cidr`, `ingress_cidr`, and `resource` (arn) flow into
   raw f-string HCL without escaping in the `terraform_resource_blocks.py` builders. A crafted
   node value with a `"` + newline breaks out and injects arbitrary HCL (reviewer-confirmed).
   Not reachable today (inputs are hardcoded generators), but this is a defensive-security tool
   whose roadmap plans LLM/`ModalBatchGenerator`/`DiffusionGraphGenerator` engines that WOULD
   feed untrusted values here.

## Goals

- **Per-family tags:** derive `common_tags` from the scenario graph (not hardcoded) so each
  family's HCL tags match its graph (`env`/`owner`/`app`).
- **Escaping:** every string attribute entering emitted HCL is safely quoted/escaped — route
  scalar string values through a single escaping helper (or `json.dumps`-style quoting, as the
  policy documents already do). A hostile node value must not break out of its HCL string.

## Approach

- `build_main_tf` (or a new graph-aware variant) reads the family's representative tags from the
  graph — e.g. from the `Account`/root node's `tags`, or the modal tag set across nodes — and
  emits those into `common_tags`. Requires threading the graph (or the derived tags) into the
  static-file builders that currently take none; keep the change minimal.
- Add a `_hcl_str(value: str) -> str` helper (single source) that returns a safely-quoted HCL
  string literal, and route every scalar value in `role_block`/`policy_block`/`vpc_block`/
  `subnet_block`/`security_group_block`/bucket builders through it. Prefer reusing the existing
  `json.dumps` quoting where a JSON document is built.
- Keep the forbidden-permission invariant: escaping must not enable a forbidden action to slip
  through (it can't — the graph-risk engine rejects those on policy nodes upstream).

## Non-Goals

- No new families, no emitter re-architecture beyond tags + escaping.
- No change to which resources are emitted (FXL-31 already handles per-family resources).

## Acceptance Criteria

- [ ] `public_data_exposure` HCL `common_tags` show `env=prod` (its graph tags); `ci_cd_iam_chain`
      shows `env=staging`. Tags are derived from the graph, not hardcoded.
- [ ] A test with a hostile node `name` (containing `"` and a newline) produces valid,
      non-injected HCL — `terraform validate` still passes and no extra/unexpected resources or
      HCL statements appear.
- [ ] All scalar string values entering HCL are escaped via the single helper.
- [ ] Regression: both families still `generate → validate` all-PASS; `terraform validate`
      passes for both; the forbidden-permission and no-real-secrets invariants hold.
- [ ] `ruff` + `mypy --strict` clean; coverage on `app` ≥80%.

## Affected Files

- `app/cloudforge/pipeline/terraform_blocks.py` (graph-derived `common_tags`)
- `app/cloudforge/pipeline/terraform_resource_blocks.py` (escaping helper + apply)
- `app/cloudforge/pipeline/terraform_emitter.py` / `artifacts.py` (thread tags/graph if needed)
- `tests/cloudforge/test_terraform_emitter.py` (per-family tags + injection tests)

## Threat Model (advisory)

The escaping change **closes** a real injection surface (HCL breakout via unescaped attribute
values) that becomes reachable the moment a generative engine feeds untrusted node data — this
is the ticket's security value. Per-family tags fix a correctness/coherence gap. No new external
surface; no secrets introduced. **Risk reduced by this ticket.**

## Dependencies

- Depends on FXL-31 (merged). No conflicts with any open work.
