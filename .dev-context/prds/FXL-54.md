# FXL-54 — OPA policy: family-agnostic critical-chain check

**Status**: Draft
**Priority**: P1
**Type**: fix
**Effort**: M
**Milestone**: M7 — Product-validity hardening
**Maps to**: GitHub issue #54

## Problem

`policies/scenario.rego` was authored during FXL-1 when `ci_cd_iam_chain` was the only
family. Its "required critical chain" rules **hardcode the ci_cd edge types** (`assumes`,
`can_pass_role`, `can_read`) as a **universal** requirement. So `cloudforge validate` on the
`public_data_exposure` family FAILs with 3 OPA denials and **exits 1** — the tool's own policy
rejects a scenario the tool generates. This was hidden behind the OPA-not-installed WARN-skip
until OPA was installed; it violates the 12-point "validated" definition (FXL-D003) — a
generated scenario must pass its own optional scanners.

`public_data_exposure`'s critical path is `exposed_to_internet → stores_sensitive_data` (no IAM
role chain), so the ci_cd-specific edges are absent and wrongly denied.

## Goal

Make the critical-chain OPA check **family-agnostic**: assert that a *coherent critical risk
path exists* for the scenario, without hardcoding one family's edge types. Both families pass;
a genuinely broken scenario still denies.

## Approach

Replace the three hardcoded-edge `deny` rules with a generic requirement. Options (pick the
cleanest that keeps ci_cd passing AND makes pde pass):
- **Preferred:** require the graph to contain at least one edge whose `security.risk` is
  `critical` AND a `stores_sensitive_data` edge (a sensitive-data sink) — both families have
  both. This asserts "there is a critical risk terminating in sensitive data" without naming
  ci_cd edges.
- Keep the other deny rules unchanged: required tags, forbidden destructive perms, resource
  budget. Those are already family-agnostic and correct.

The stdlib graph-risk engine already validates the *specific* ground-truth path per scenario
correctly; the rego only needs to stop hardcoding ci_cd and do a generic sanity check.

## Non-Goals

- No change to the graph-risk engine, the families, the emitter, or the scorer.
- Not trying to make the rego re-derive each family's exact path (the Python engine owns that);
  the rego is a coarse, family-agnostic sanity gate.

## Acceptance Criteria

- [ ] `cloudforge validate` on BOTH families exits **0** with OPA installed (`[PASS] opa policy`
      for `public_data_exposure` AND `ci_cd_iam_chain`).
- [ ] The policy still DENIES a genuinely broken scenario: a graph with no critical-risk edge /
      no sensitive-data sink, missing required tags, a forbidden destructive perm, or over the
      resource budget still triggers a deny (add/keep tests via `opa eval` fixtures).
- [ ] A regression test (or the validate flow) covers pde-with-opa passing and ci_cd-with-opa
      passing.
- [ ] No change to the non-chain deny rules (tags / forbidden perms / budget).

## Affected Files

- `policies/scenario.rego` (replace the 3 hardcoded-edge deny rules with a family-agnostic one)
- A test exercising `opa eval` over both families' graphs + a broken graph (e.g.
  `tests/cloudforge/test_opa_policy.py`, or extend the validate-orchestrator tests). Since OPA
  is installed locally, a real `opa eval` test is feasible; gate it on `opa` presence (fail-soft
  skip if absent, like the terraform tests).

## Threat Model (advisory)

This fixes a validation-integrity defect (a generated scenario failing its own policy). No new
surface; the policy still denies genuinely-unsafe scenarios. **Risk reduced** (removes a false
rejection while keeping the real guards).

## Dependencies

- Independent of all other work. OPA installed locally.
