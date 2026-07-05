# FXL-39 — Emitter: sanitize node.id at resource-label position + total derive_common_tags

**Status**: Draft
**Priority**: P3
**Type**: fix
**Effort**: S
**Milestone**: M2 — Terraform emitter
**Maps to**: GitHub issue #39
**Surfaced by**: AI review gate on PR #38 (two accepted, out-of-scope nits)

## Problem

Two defense-in-depth gaps in the graph-driven emitter, both about untrusted node values.
Neither is reachable with the two hardcoded generator families, but both become live the
moment a generative engine (LLM/`ModalBatchGenerator`/`DiffusionGraphGenerator`, on the
roadmap) feeds node data. FXL-35 closed HCL *string-value* injection via `hcl_str`; these
are the remaining surfaces `hcl_str` cannot cover.

1. **Resource-LABEL injection via `node.id`.** `terraform_resource_blocks.py::resource_name`
   does only `node.id.replace("-", "_")`. A hostile id like `a" { evil }` breaks out of the
   Terraform resource-label position (`resource "aws_vpc" "a" { evil }" {...}` — malformed
   HCL). Terraform identifiers are NOT json-quotable, so `hcl_str` can't fix this — the label
   itself must be sanitized to the legal identifier charset.
2. **`derive_common_tags` not total on an empty graph.** `terraform_blocks.py` does
   `nodes[0]` as a fallback, raising `IndexError` on `[]`, despite the docstring claiming
   totality "for graphs without an Account node."

## Goals

- `resource_name` returns a Terraform-legal identifier for ANY `node.id`: keep only
  `[A-Za-z0-9_]` (map others to `_`), and ensure it can't be empty or start with a digit
  (Terraform labels must start with a letter/underscore).
- `derive_common_tags([])` does not raise — return a safe default `NodeTags` (or a
  documented sentinel) and fix the docstring to match actual behavior.

## Non-Goals

- No change to `hcl_str` (FXL-35 covers string values), no emitter re-architecture, no new
  families/resources.

## Approach

- `resource_name`: `re.sub(r"[^A-Za-z0-9_]", "_", node.id)`, then guarantee a valid leading
  char (prefix `_` if it starts with a digit or is empty). Keep it a small pure function.
- `derive_common_tags`: guard the empty case before `nodes[0]` — return a documented default
  `NodeTags` (e.g. `env="unknown", owner="unknown", app="unknown"`), and correct the docstring.

## Acceptance Criteria

- [ ] A node whose `id` contains `"`, `{`, `}`, newline, or spaces produces VALID, single-block
      HCL — a hostile-id test asserts `terraform validate` passes and no extra/injected block
      appears; the label is a legal identifier.
- [ ] `resource_name` output always matches `^[A-Za-z_][A-Za-z0-9_]*$`.
- [ ] `derive_common_tags([])` returns a `NodeTags` and does not raise; docstring matches.
- [ ] Regression: both families still `generate → validate` all-PASS; `terraform validate`
      passes for both; per-family tags unchanged (pde=prod, ci_cd=staging); no forbidden
      actions; existing `hcl_str` interpolation tests still pass.
- [ ] `ruff` + `mypy --strict` clean; coverage on `app` ≥80%.

## Affected Files

- `app/cloudforge/pipeline/terraform_resource_blocks.py` (`resource_name` sanitization)
- `app/cloudforge/pipeline/terraform_blocks.py` (`derive_common_tags` empty guard + docstring)
- `tests/cloudforge/test_terraform_emitter.py` (hostile-id test + empty-nodes test)

## Threat Model (advisory)

Closes the two remaining untrusted-node-value surfaces the FXL-35 review identified, hardening
the emitter against future generative engines. No new external surface; no secrets. **Risk
reduced.**

## Dependencies

- Depends on FXL-31 + FXL-35 (both merged). No conflicts with any open work.
