# FXL-N4 Result — Per-type dedup in the Terraform emitter

**Status**: DONE (PR open, CI green, NOT merged)
**PR**: #53 — https://github.com/spivi/forge-x-labs/pull/53 (Closes #47)
**Branch**: `fix/FXL-N4-emitter-dedup` (based on `origin/master`)
**Commit**: `a910b69` — `fix(FXL-N4): reject duplicate Terraform resource labels pre-emission`
**PR state**: OPEN · MERGEABLE · all 4 CI checks SUCCESS (2× lint-and-type-check, 2× test)

## Problem
`identifiers.resource_name(node)` sanitizes `node.id` to a Terraform-legal label
(`[^A-Za-z0-9_]` → `_`, leading-char guard). Distinct ids differing ONLY by an
illegal-char / `-` / `_` swap collapse to the SAME label (`a-b` and `a_b` both → `a_b`).
Terraform then errors on a duplicate resource label (`Duplicate resource "aws_s3_bucket"`),
a `terraform validate` DoS on externally/generatively-authored graphs (FXL-39 follow-up).

## Solution
Pre-emission collision check that fails loud (reject, do NOT uniquify — a generator
producing collisions is a generator bug), naming BOTH colliding node ids + the shared label.

## Scoping choice: PER-TYPE (not global) — rationale
Chose **per emitted resource TYPE** scoping. Terraform labels only collide within the same
`resource "<type>"` namespace, so `a_b` as an `aws_s3_bucket` label and `a_b` as an
`aws_iam_role` label do NOT clash. Per-type is the **correct** scope: a global
over-approximation (reject any two ids colliding on label at all) would raise FALSE POSITIVES
on legitimately distinct-type nodes that happen to share a label. Per-type costs little extra
code — a static `NodeType → resource_type` map mirroring the block assemblers in
`terraform_blocks.py`. Node types that emit no resource (Account / CICDIdentity / Application /
DataSet / LogTrail) carry no label and are skipped. Recorded as decision **FXL-D006**.

## Files
- **NEW** `app/cloudforge/pipeline/label_collisions.py` — `check_label_collisions(nodes)` +
  `NodeType → Terraform resource-type` map; raises `GraphIntegrityError` naming both ids,
  the shared label, and the resource type.
- `app/cloudforge/pipeline/terraform_emitter.py` — call `check_label_collisions` first in
  `emit()`, before any file is written.
- `app/cloudforge/cli.py` — moved `write_all` INSIDE the existing `except CloudforgeError`
  block so a `GraphIntegrityError` at emit surfaces as a clean `error: …` exit-1, not a raw
  traceback (the pre-existing catch only wrapped generate/mutation, not the emitter).
- `tests/cloudforge/test_terraform_emitter.py` — 5 new tests (colliding-graph guard).
- `tests/cloudforge/test_cli.py` — 1 new CLI test (clean error on colliding graph).
- `.dev-context/DECISIONS.md` — FXL-D006.

## Tests (TDD: colliding-graph test written first, failed, then implemented)
- `test_colliding_ids_same_type_raise_graph_integrity_error` — **the colliding-graph test**:
  constructs two `S3Bucket` nodes `a-b` / `a_b` → asserts `GraphIntegrityError` naming BOTH
  ids (`a-b`, `a_b`) and the shared label `a_b`. (NOT a raw terraform failure.)
- `test_colliding_ids_rejected_before_any_file_is_written` — no partial `.tf` tree left behind.
- `test_colliding_labels_across_different_types_do_not_collide` — per-type scoping proof
  (S3 `a_b` + IAM-role `a_b` emit fine).
- `test_non_emitting_node_types_never_trigger_a_collision` — Account/CICDIdentity skipped.
- `test_shipped_families_emit_without_false_positive_collision` — both real families emit
  all six files (regression).
- `test_generate_on_colliding_graph_exits_with_clean_error` (CLI) — colliding graph → exit 1,
  `error:` message names both ids, `Traceback` NOT present.

Test count: **6 new tests** (+ new `label_collisions.py` at 100% coverage).

## Validation results
- `ruff check app/ tests/cloudforge/ tests/security/ --fix` → **All checks passed**
- `ruff format` → clean (note: local .venv ruff 0.8.6 reverts FXL-N2's CI-matching parens
  style on the two pre-existing `tests/security/` files — the tracked #52 divergence — so those
  files were `git restore`d; my files are format-clean under CI's newer ruff, confirmed green).
- `mypy --strict app/` → **Success: no issues found in 38 source files**
- Full suite: **752 passed, coverage 95.64%** (≥80% gate). `label_collisions.py` 100%,
  `terraform_emitter.py` 100%.
- **CI (PR #53)**: all 4 checks SUCCESS — lint-and-type-check (CI's newer ruff accepts the
  code, no #52 hit) + test.

### Real e2e
- Both families `generate` → exit 0 (no false-positive collision).
- Both families `terraform validate` → **[PASS] terraform validate** (no duplicate-resource
  error; emitter produces valid HCL).
- Colliding graph → fails at `generate` time with the clean
  `GraphIntegrityError: duplicate Terraform resource label 'a_b' for resource "aws_s3_bucket":
  node ids 'a-b' and 'a_b' both sanitize to it …`, NOT a terraform crash.

## Notes / non-blockers
- `public_data_exposure`'s `cloudforge validate` exits 1 due to a PRE-EXISTING
  `[FAIL] opa policy. 3 deny rule(s) triggered` outcome — its own `terraform validate` line
  PASSES. This is unrelated to FXL-N4: the diff touches nothing in `policies/`,
  `app/cloudforge/validate/`, or `app/cloudforge/generate/`. The FXL-N4-relevant invariant
  (both families still terraform-validate; no false-positive collision) holds.
- One transient full-suite flake (`no space left on device` from accumulated per-test
  `terraform init` provider downloads filling `/tmp`) was resolved by clearing stale pytest
  temp dirs; a shared `TF_PLUGIN_CACHE_DIR` made the full run deterministic (752 passed).
  Environment-only, not a code issue.

## Blockers
None. PR #53 green and mergeable; NOT merged per instructions.
