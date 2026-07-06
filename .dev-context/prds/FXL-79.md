# FXL-79 — OPA critical-chain check: existence vs. connectivity (defense-in-depth)

**Status**: Ready
**Priority**: P3
**Type**: chore
**Effort**: S
**Milestone**: M7 — Product-validity hardening
**Maps to**: GitHub issue #79

## Problem

The family-agnostic OPA predicate (from FXL-54) requires a critical-risk edge AND a
`stores_sensitive_data` sink to **exist**, but does not require they lie on a **shared reachable
path**. So a graph with a critical edge and a sink on *disconnected components* — or a `ci_cd` graph
with `can_pass_role` cut but `can_read` intact — passes the OPA check. This is **by-design
coarseness**: per-path reachability is owned by the Python graph-risk engine (`validate/graph_risk.py`),
which DOES validate the ground-truth path per family. So a genuinely-broken scenario is still caught
by `validate` overall — this is **not a false-negative in the full pipeline**, only in the rego
considered in isolation.

## Goal

Close (or consciously accept) the defense-in-depth gap between the coarse rego check and the precise
graph-engine check, WITHOUT re-coupling the rego to specific scenario families.

## Approach (decision-first)

The core tension: adding per-path reachability to the **rego** would re-hardcode family edge types —
exactly the coupling FXL-54 removed. Rego is a coarse, family-agnostic sanity gate by design.
Reachability is graph traversal, which is the **Python engine's** job. So the honest options, in
preference order:

1. **Preferred — document the layering as intentional + add a connectivity assertion to the GRAPH
   ENGINE (not the rego).** Add a graph-risk check that asserts the critical-risk edge and a
   `stores_sensitive_data` sink share a reachable path (a small BFS/DFS reusing the engine's existing
   adjacency, family-agnostic). The rego stays coarse; the engine gains the defense-in-depth. Record
   the "rego = coarse gate, engine = precise path" split as a decision (extend FXL-D003/the OPA note).
2. **Minimal — document-only.** If the graph engine's existing ground-truth-path check already
   fully covers this (it validates the declared critical path per scenario), then the gap is purely
   theoretical for generated scenarios (which always declare a coherent path). In that case, close as
   **won't-fix-in-rego** with a written rationale + a test asserting the disconnected-components graph
   is rejected by `validate` overall (proving the engine catches what the rego doesn't).

The implementer picks (1) vs (2) based on whether `graph_risk.py` already rejects a
critical-edge-and-sink-on-disconnected-components graph. If it does → (2). If it doesn't → (1).

## Non-Goals

- **Do NOT add per-path reachability to `policies/scenario.rego`** — that re-couples it to families
  (regression of FXL-54). The rego stays a coarse, family-agnostic existence gate.
- No change to the two scenario families, the emitter, or the scorer.

## Acceptance Criteria

- [ ] A graph with a critical-risk edge and a `stores_sensitive_data` sink on **disconnected
      components** is either (a) rejected by the graph engine's new connectivity check, or (b) shown
      by a test to be rejected by `validate` overall — with a written rationale for which path was
      taken.
- [ ] The OPA rego is **unchanged** (or only its comment clarifies it is a coarse existence gate) —
      no family edge types hardcoded back in.
- [ ] A test covers the disconnected-components case (offline; `opa`-gated or engine-only).
- [ ] A DECISIONS.md entry (or an extension of the OPA note) records the "rego coarse / engine
      precise" layering.
- [ ] ruff + mypy --strict clean; bare `pytest tests/cloudforge/ -q --no-cov` green.

## Affected Files

- `app/cloudforge/validate/graph_risk.py` (option 1: add a family-agnostic connectivity check)
- `tests/cloudforge/test_graph_risk.py` or the validate-orchestrator tests (the disconnected case)
- `.dev-context/DECISIONS.md` (record the layering decision)
- `policies/scenario.rego` (comment-only clarification, if any — NO logic re-coupling)

## Threat Model (advisory)

This is a **validation-integrity hardening** ticket — it tightens (or documents) a defense-in-depth
layer. No new surface. It reduces the chance a genuinely-broken scenario slips through, strictly
**risk-reducing**. The explicit non-goal (don't re-couple the rego) preserves the family-agnostic
property FXL-54 established.

## Dependencies

Independent. `opa` is installed locally (fail-soft skip if absent, per the existing tests).
