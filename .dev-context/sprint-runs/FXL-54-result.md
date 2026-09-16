# FXL-54 — OPA policy: family-agnostic critical-chain check — RESULT

**Status**: DONE (implemented, tested, PR open — NOT merged, per instructions)
**PR**: #78 — https://github.com/spivi/forge-x-labs/pull/78 (Closes #54)
**Branch**: `fix/FXL-54-opa-family-agnostic` (based on origin/master)
**Type**: fix · **Priority**: P1 · **Milestone**: M7

## Rego change summary (`policies/scenario.rego`)

Removed the three **hardcoded-edge** critical-chain deny rules (family-specific to
`ci_cd_iam_chain`):

- `has_assume` + deny "missing required 'assumes' edge"
- `has_passrole` + deny "missing required 'can_pass_role' edge"
- `has_sensitive_read` + deny "missing required 'can_read' edge"

Replaced with a **family-agnostic** predicate — the graph must contain:

- **(a)** at least one edge whose `security.risk == "critical"`, AND
- **(b)** at least one `stores_sensitive_data` sink edge.

New rules:
- `has_critical_edge` → deny `"no critical-risk edge — scenario has no coherent critical risk path"`
- `has_sensitive_sink` → deny `"no 'stores_sensitive_data' edge — critical risk has no sensitive-data sink"`

**Why both real families pass but a broken graph fails** (verified by inspecting each
generated `graph.json`):
- `ci_cd_iam_chain`: `can_pass_role` / `can_read` / `stores_sensitive_data` are risk `critical`, and `stores_sensitive_data` sink present. ✅
- `public_data_exposure`: `exposed_to_internet` + `stores_sensitive_data` are risk `critical`, and `stores_sensitive_data` sink present. ✅
- A graph with every critical edge downgraded, or with the `stores_sensitive_data` sink stripped, is denied. ✅

The **non-chain** deny rules (required tags, forbidden destructive perms, resource
budget ≤ 40) are **UNCHANGED**.

## Acceptance criteria — all met

- [x] **Both families `[PASS] opa policy` + exit 0** (opa installed locally, real `cloudforge validate`):
  - `public_data_exposure`: was `[FAIL] opa policy. 3 deny rule(s) triggered` → exit 1; now `[PASS] opa policy` → **exit 0**.
  - `ci_cd_iam_chain`: `[PASS] opa policy` → **exit 0** (regression preserved).
- [x] **Broken graph still denies** — real `opa eval` confirms a deny for each of: no-critical-risk-edge, no-sensitive-data-sink, missing-required-tag, forbidden-destructive-perm, over-resource-budget.
- [x] **Test covers pde-with-opa PASSING and ci_cd-with-opa PASSING** — real `opa eval` over each family's generated `graph.json`, gated on `shutil.which("opa")` (skip fail-soft if absent, mirroring the terraform tests).
- [x] **No change to non-chain deny rules** — tests `test_missing_required_tag_still_denies`, `test_forbidden_destructive_perm_still_denies`, `test_over_resource_budget_still_denies` confirm they still fire.

## Test

`tests/cloudforge/test_opa_policy.py` (7 tests, all real `opa eval`, gated on opa presence):

- `test_public_data_exposure_graph_has_no_denials` (was FAILING pre-fix — proved the bug via TDD)
- `test_ci_cd_iam_chain_graph_has_no_denials`
- `test_no_critical_risk_edge_denies`
- `test_no_sensitive_data_sink_denies`
- `test_missing_required_tag_still_denies`
- `test_forbidden_destructive_perm_still_denies`
- `test_over_resource_budget_still_denies`

TDD confirmed: pre-fix the two "no denials" cases FAILED for pde; post-fix all 7 pass.
With opa absent (simulated CI), all 7 **SKIP cleanly** — CI stays green.

## Local validation

- `ruff check` (app/, tests/cloudforge/, tests/security/): **All checks passed**
- `ruff format --check` on changed files: clean; `opa fmt --diff`: no diff
- `mypy --strict app/`: **Success, no issues (38 files)**
- `pytest tests/cloudforge/ -m 'not stress' --no-cov`: **116 passed, 5 deselected**
- `pytest tests/security/ --no-cov`: **424 passed**
- `pytest tests/cloudforge/test_opa_policy.py`: **7 passed** (opa present) / **7 skipped** (opa absent)

## CI status

**GREEN** — 4/4 checks SUCCESS, 0 failed. `lint-and-type-check` pass, `test` pass.
PR `mergeStateStatus: CLEAN`, `mergeable: MERGEABLE`. The opa test skips fail-soft in
CI (no opa installed), as designed.

## Scope discipline

Diff is exactly 2 files: `policies/scenario.rego` + new `tests/cloudforge/test_opa_policy.py`.
(Reverted incidental `ruff format` churn on 3 unrelated pre-existing test files to keep
the PR scoped.) No change to the graph-risk engine, families, emitter, scorer, mutation,
or the other deny rules. Committed with `--signoff`; no `--no-verify`.

## Blockers

None. PR open and green; NOT merged (per instructions).
