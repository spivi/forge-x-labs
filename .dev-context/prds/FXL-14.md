# FXL-14 — Mutation Engine (`MutationGenerator`)

**Status**: Draft
**Priority**: P2
**Type**: feature
**Effort**: M (3–5 files)
**Milestone**: M5 — Mutation engine
**Maps to**: GitHub issue #14

## Problem / Motivation

The MVP ships one deterministic scenario (`ci_cd_iam_chain`). For scanner benchmarking we
need **diversity** — many labeled variants of the same underlying risk so a scanner can't
overfit to one exact graph. A `MutationGenerator` produces seeded variants (renamed
resources, shuffled/extra tags, benign resource additions) **without changing the
ground-truth risk**, so the critical path and expected findings still hold.

## Goals

- A `MutationGenerator` behind the existing `ScenarioGenerator` interface (no pipeline
  changes) that takes a base `ScenarioBundle` + a seed and returns a mutated bundle.
- Deterministic and **seedable** (same seed → same output; reproducible benchmarks). No
  `random`/`Math.random`-style nondeterminism leaking into artifacts.
- Mutations preserve ground truth: node **ids** referenced by ground-truth paths/findings
  are stable; only display `name`s, `tags`, and benign extra nodes/edges change.
- The risk engine must still PASS on every mutated variant (critical path intact, no
  forbidden perms introduced, broad grants still documented).

## Non-Goals

- No LLM/diffusion generation (that's a separate future engine).
- No structural changes to the critical risk chain (mutations are cosmetic + additive
  benign context only).
- No new scenario family (that's FXL-26).

## Approach

- New module `app/cloudforge/generate/mutation_generator.py` with
  `class MutationGenerator` taking `(base: ScenarioBundle, seed: int)`.
- Seeded, pure transforms in a small helper (e.g. `mutation_ops.py`) if the module nears
  200 lines: rename map for node `name`s, tag jitter (add/reorder non-identifying tags),
  optional benign node/edge injection (e.g. an extra unused subnet) within `max_resources`.
- Use a seeded `random.Random(seed)` instance passed explicitly (no global RNG) so output
  is reproducible and mypy-clean.
- Optional CLI surface: `cloudforge generate ... --mutate-seed N` (thin; delegates).

## Acceptance Criteria

- [ ] `MutationGenerator(base, seed).generate()` returns a valid `ScenarioBundle`.
- [ ] Same seed → byte-identical graph.json; different seed → different `name`s/tags but
      identical node **ids** on the ground-truth path.
- [ ] `GraphRiskEngine` returns all-PASS on ≥3 distinct seeded variants (parametrized test).
- [ ] No mutation introduces a forbidden permission or breaks broad-grant documentation.
- [ ] `ruff` + `mypy --strict` clean; coverage on `app` stays ≥80%.

## Affected Files

- `app/cloudforge/generate/mutation_generator.py` (new), optional `mutation_ops.py` (new)
- `app/cloudforge/generate/template_generator.py` or `cli.py` (wire the seed option)
- `tests/cloudforge/test_mutation_generator.py` (new)

## Threat Model (advisory)

Attack surface: none external — this is a local, offline generator. Relevant OWASP-style
risks are limited to **output integrity**: (1) a mutation must never introduce a real
destructive permission (mitigated — the risk engine's forbidden-permission check runs on
every variant and FAILs); (2) determinism must not depend on wall-clock/PID (mitigated —
explicit seeded RNG, no `Date.now()`); (3) mutated tags must not smuggle secrets
(mitigated — `no_real_secrets` constraint + tag values drawn from a fixed benign vocab).
No auth, network, PII, or LLM surface. **Residual risk: low.**

## Dependencies

- Depends on the shipped `ScenarioGenerator` interface + `GraphRiskEngine` (both merged).
