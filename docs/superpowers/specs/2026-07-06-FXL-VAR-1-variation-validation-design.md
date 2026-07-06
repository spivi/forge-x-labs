# FXL-VAR-1 — Large-Scale Scenario Variation Validation (Combined: Generator Depth + Harness)

**Date:** 2026-07-06
**Status:** Design approved (brainstorm) — pending spec review, then implementation plan
**Epic type:** Functionality validation at scale. **Not** ML / diffusion / Modal / cloud deployment.

---

## 1. Problem & premise correction

The original FXL-VAR-1 proposal asked: *"Can cloudforge generate structurally different
cloud-risk environments, not just cosmetically renamed copies?"* and specced a **measurement
harness** to find out.

**The code already answers the question.** Investigation (2026-07-06) confirms the generators are
fully hardcoded:

- `TemplateGenerator.generate()` ignores everything in the spec except `scenario_type` and returns
  a **fixed literal graph** (`ci_cd_iam_chain` = a hardcoded 14-node graph; `public_data_exposure`
  similar). No seed, scale, or topology parameter reaches the builders.
- The `MutationGenerator` is **cosmetic by explicit design** — its docstring: mutations are
  "cosmetic (display `name`/`tags`) or benign-additive (an unused subnet); node `id`s and every
  ground-truth-relevant edge are left untouched." One spare subnet is the entire topology story.
- `ScenarioSpec.Requirements` *already declares* `critical_chains`, `medium_findings`,
  `false_positives` — but the builders ignore them. The intent to parameterize was designed in;
  it was never honored.

Mapped to the proposal's own three-level variation model:

| Level | Proposal's guess | Actual state |
|---|---|---|
| Cosmetic (names/tags) | "probably covered" | ✅ covered (mutation engine) |
| Benign topology (extra apps/buckets/roles) | "partially covered or missing" | ❌ 1 hardcoded spare subnet only |
| Risk-shape (path length, decoys, FPs, controls) | "likely the real gap" | ❌ fully hardcoded — zero variation |

Building the harness alone would faithfully report **~1 graph-shape signature per family** — a
correct but known-in-advance result. Per the user decision, this epic is **combined**: add
generator depth AND the harness that proves it, with the harness's diversity thresholds serving as
the acceptance test for the depth work. Measurement and subject are co-designed so they cannot drift.

## 2. Goal & non-goals

**Goal:** Prove cloudforge can generate many large, diverse, valid, benchmarkable cloud-risk
environments while preserving ground truth and the hard safety boundaries — by (a) making the
generators produce real topology + risk-shape variation and (b) building a variation harness that
measures and gates that variation at scale.

**Non-goals (explicit):** cloud deployment, `terraform apply`, live account inspection, ML, LLM
generation, Modal, diffusion, internet crawling, new learning-corpus source adapters, offensive
procedure generation. No ML/diffusion stubs or half-built model interfaces — only a clean seam.

## 3. Architecture

**Core principle: a `ScenarioBlueprint` is the single source; graph + ground-truth + findings are
*projections* of it.** Today ground-truth agreement is free because one hardcoded literal is the
single source. This design preserves that property under parameterization by assembling scenarios
from typed **fragments**, each of which *owns* its node ids, edges, findings, and ground-truth
entries. Artifacts cannot disagree by construction; the existing model validators + stress-hardened
checks remain the backstop.

```
ScenarioSpec (+ scale_profile, variation_axes)
        │
        ▼
  GraphComposer(seed)          ← deterministic: same seed = byte-identical
        │  seeded fragment PLAN → instantiate fragments (ids namespaced per instance)
        ▼
  ScenarioBlueprint            ← the ONE source (owns ids)
     ├── graph            (projection)
     ├── ground_truth     (projection — path fragments carry their own node/edge keys)
     └── findings         (projection — each fragment carries its own findings)
        │
        ▼   existing validate/ + report/ + terraform_emitter unchanged downstream
```

### 3.1 Engine seam (SD-future boundary — approved)

`GraphComposer` sits **behind the existing `ScenarioGenerator` protocol** (`generate/base.py`) as
one engine (`ComposerGenerator`), a sibling to `TemplateGenerator`. `base.py` already documents the
intent: *"new engines (LLM, diffusion) implement `ScenarioGenerator` separately."*

Consequences:
- Everything downstream of `ScenarioBundle` (validate, report, Terraform emitter, scanner scoring,
  **and the entire FXL-VAR-1 harness**) is engine-agnostic. The harness measures **any** engine —
  including a future `DiffusionGenerator` — for free.
- The **fragment registry is a named, addressable vocabulary** (typed fragments + parameters), not
  just internal functions. This is precisely the safe substrate a learned generator decodes into: a
  diffusion model would *steer* which fragments/counts/shape; the substrate *guarantees* validity
  and non-deployability. Building depth-via-fragments now is what makes learned generation tractable
  and safe later — not a detour.
- **This epic builds no diffusion/ML/latent code.** It only keeps the seam clean and the vocabulary
  addressable.

### 3.2 Alternatives rejected

- *Extend the mutation engine (post-hoc mutation of the hardcoded graph):* mutation is cosmetic by
  design; adding risk-shape means re-deriving ground truth — the exact fragile path the stress bugs
  came from.
- *Free-form random graph generation:* cannot guarantee ground-truth validity or non-deployability;
  fights every stress-hardened invariant.
- *Fragment composition (chosen):* each fragment independently valid + testable; variation = which
  fragments + params; ground truth travels with the fragment that owns it. Smallest change that
  makes structural variation safe, and the substrate learned generation needs.

## 4. Components

### 4.1 Depth layer (`app/cloudforge/generate/`)

- **`fragments/` — addressable safe-vocabulary.** Registry of typed fragments; each is a pure
  `(rng, params) -> FragmentBundle` owning its own ids/edges/findings/ground-truth. Kinds:
  - `core.*` — the risk path (existing two families become `core.ci_cd_iam_chain` /
    `core.public_data_exposure`, now parameterized by path length + branching).
  - `decoy.*` — extra risky-*looking* paths that are not the ground-truth path.
  - `false_positive.*` — public-looking-but-denied / broad-looking-but-constrained (owns a `benign`
    finding).
  - `compensating_control.*` — explicit deny, scoped condition, private network, logging-present.
  - `benign_noise.*` — unrelated buckets/roles/apps/subnets (no findings, no ground-truth).
- **`GraphComposer` (`ComposerGenerator`)** — implements `ScenarioGenerator`. Given `(spec, seed)`:
  reads scale + axes → seeded fragment plan → instantiate (per-instance **id namespacing**, e.g.
  `decoy2/role-x`, asserted unique) → assemble `ScenarioBlueprint` → project graph/GT/findings.
- **`ScaleProfile`** — maps `tiny/small/medium/large/xlarge` to node/resource budget bands; composer
  adds `benign_noise` + `decoy` fragments until in-band then stops (deterministically). `xlarge` is
  graph-only by default (no Terraform).

### 4.2 Harness layer (`app/cloudforge/variation/`)

- **`models.py`** — `VariationSpec` (families, seed_start/count, scale_profiles, variation_axes,
  constraints, validation/scanner/report profiles) + `Manifest`/run-artifact models.
- **`suite_runner.py`** — per `(family × scale × seed)`: compose → validate → optional scanner-score
  → report; writes the run tree; honors `max_failures_before_abort`.
- **`diversity.py`** — graph-shape signature (sorted node-type counts, sorted edge-type counts,
  critical-path length, finding families, presence of decoys/FPs/compensating-controls, family —
  **names/tags excluded**) + `diversity_report.json`.
- **`replay.py`** — regenerate one scenario into a temp dir; hash `graph.json` /
  `expected_findings.json` / `ground_truth_paths.json`; compare to manifest.
- **`minimize.py`** — on failure: preserve raw artifacts + logs + exception; shrink (smaller scale,
  disable one axis at a time) to smallest reproducer; never delete failing artifacts.
- **`summary.py` / `report.py`** — suite-level rollup + human-readable variation-run report.

### 4.3 Reused unchanged

`validate/`, `report/`, `pipeline/terraform_emitter`, scanner scoring — all operate on
`ScenarioBundle`; no changes. `diversity.py`/`replay.py` operate only on bundle artifacts, never on
generator internals (keeps the harness engine-agnostic).

## 5. Data flow & acceptance gate

Per-scenario: `spec+scale+axes+seed → GraphComposer.generate() → ScenarioBundle → validate /
terraform_emitter (skip xlarge; TF validate = init -backend=false, never apply) / scanner_score
(checkov if present else WARN) / report → suite_runner writes tree + appends manifest`.

Determinism holds because the **seeded fragment plan is the only randomness** (`Random(seed)`);
`replay.py` re-runs it and compares hashes.

**Acceptance gate (Phase 3 — thresholds ARE the depth acceptance test), per family:**

| Threshold | Meaning |
|---|---|
| ≥ 5 distinct graph-shape signatures | real topology variation, not renames |
| ≥ 4 distinct critical-path lengths *(where family supports it)* | risk-shape variation |
| ≥ 3 scanner-score profiles *(if checkov present)* | detection variation |
| ≥ 20% scenarios include decoys | benign-topology depth |
| ≥ 20% include compensating controls | risk-shape depth |
| ≥ 10% include false positives / near-misses | near-miss depth |

If a fragment kind is missing, the gate **fails loudly**. Where a family genuinely can't support an
axis, it is recorded as **`unsupported`** in the diversity report (honest), not silently skipped.

## 6. Error handling, safety & determinism

**Safety (hard, inherited from stress epic):**
- `no_apply`/`no_credentials` enforced **structurally** — no code path shells out to
  `terraform apply` (an absence, not a toggle). TF validation only `init -backend=false` + `validate`.
- Every composed scenario passes `deployable: false` + no-forbidden-permissions **before** it is
  written; a fragment introducing a destructive permission is rejected at compose time.
- Fragments draw from **fixed benign vocabularies** (`no_real_secrets` discipline extended to every
  fragment) — no free text into names/tags/actions.
- All writes go through hardened `io/paths.py` output-root confinement (stress path-traversal fix);
  the harness adds no new write primitive.

**Error classes — never collapsed (S15 lesson):**

| Class | Trigger | Behavior |
|---|---|---|
| **FAIL** | integrity/schema/config error, broken invariant | recorded failed; artifacts+logs+exception preserved; minimization attempted; counted separately |
| **WARN** | optional tool (checkov/OPA/terraform) absent | passes; capability marked "not scored" — never silently "passed" |
| **ABORT** | `max_failures_before_abort` exceeded | suite stops; partial run preserved + summarized |

A run with 0 FAILs but unmet diversity thresholds is reported as **"generators produce cosmetic
variation only"** with follow-up tickets auto-listed — never as success.

**Determinism defenses:** sort/order everywhere output is hashed (dict/set ordering is the classic
silent non-determinism source); per-instance id namespacing asserted unique before projection; no
wall-clock/PID/global RNG in the deterministic path (`run_id`/timestamps passed in, never generated
inside).

## 7. Testing strategy (TDD, 80% coverage bar)

1. **Fragment unit tests** — each fragment's `FragmentBundle` is internally valid (findings ref only
   own ids, GT edges resolve, no forbidden perms).
2. **Composer determinism** — same `(spec, seed)` → byte-identical artifacts (property-style over a
   seed range); different seeds → different shape signatures.
3. **Composer integrity** — every composed scenario passes the *full existing validator suite* (the
   regression net that ground-truth agreement holds under composition).
4. **Scale-profile bounds** — counts land in each profile's band; `xlarge` emits no Terraform.
5. **Diversity math** — signatures exclude names/tags (two cosmetically-different seeds → same
   signature); decoy/FP/control detection accurate.
6. **Gate tests** — a shallow spec **fails** the gate; a rich spec passes; an unsupported axis is
   reported as `unsupported`, not counted.
7. **Replay + minimize** — replay detects a byte-diff; minimize shrinks a seeded failure and never
   deletes artifacts.
8. **Harness smoke** — `smoke` profile runs end-to-end in CI without credentials/optional tools.

`smoke`/`ci` profiles double as living integration tests; `large`/`xlarge` are manual/nightly.

## 8. CLI & profiles

Typer subcommands (flat fallback if nested groups are awkward):
`cloudforge variation run <spec.yaml> --out <dir>` · `variation summarize <dir>` ·
`variation replay <dir> --scenario-id <id>` · `variation minimize-failure <dir>/failures/<id>`.

Example specs: `examples/variation/aws_smoke.yaml`, `aws_ci.yaml`, `aws_large.yaml`.

| Profile | Families | Scales | Seeds/each | Use |
|---|---|---|---|---|
| smoke | 2 | tiny | 5 | quick local |
| ci | 2 | tiny + small | 25 | PR/CI, no creds |
| large | 2 | tiny/small/medium/large | 250 | manual/nightly (≥2,000 scenarios) |
| xlarge (optional) | 2 | graph-only, 1,000+ nodes | — | prove graph validator/summarizer scale |

## 9. Run output tree

```
out/variation_runs/<run_id>/
  variation_spec.yaml  manifest.json  summary.json  diversity_report.json
  validation_report.json  scanner_score_summary.json
  failures/{raw,minimized}/
  scenarios/<scenario-id>/
    scenario.yaml graph.json expected_findings.json ground_truth_paths.json
    terraform/ scanner_results/ scanner_score.json report.md
```
`manifest.json` per scenario: id, family, seed, scale, axes used, artifact paths, generation
duration, validation status, scanner-score status, failure id if failed.

## 10. Acceptance criteria

1. smoke generates/validates/reports all scenarios.
2. ci runs locally without cloud credentials.
3. large supports ≥ 2,000 scenarios (2 families × 4 scales × 250 seeds).
4. Same-seed replay proves byte-identical key artifacts.
5. Diversity report proves **structural** variation, not name/tag only — gate thresholds met.
6. Unsupported variation axes honestly reported.
7. Every failure captured with seed/family/scale/axes/logs/artifacts.
8. Scanner scoring runs when checkov present; degrades clearly (WARN) when absent.
9. TF validation uses `init -backend=false` + `validate`, never apply.
10. Reports generated for all passing scenarios.
11. Suite-level report summarizes generation/validation/scanner coverage, diversity, failure classes.
12. Docs explain smoke/ci/large profiles + how to interpret the diversity report.

## 11. Honesty rule (non-negotiable)

If depth work cannot meet a threshold for a family, **do not fake success.** Record the limitation
in the diversity report and file follow-ups (topology expansion, risk-shape expansion,
family-specific axes, larger graph generation). Final epic summary must state: profiles added,
scenarios generated, pass/fail counts, diversity metrics, unsupported axes, bugs found/fixed, and
whether the system is ready for more families or still needs generator depth.

## 12. Phasing (single epic, sequenced)

- **Phase 1 — Depth:** fragment registry + `GraphComposer`/`ComposerGenerator` + scale profiles;
  the two existing families become parameterized `core.*` fragments (seed-0 = current baseline).
- **Phase 2 — Harness:** `variation/` package, CLI, run-tree, diversity metrics, replay, minimize.
- **Phase 3 — Gate:** wire diversity thresholds as the depth acceptance test; honesty reporting;
  docs.
