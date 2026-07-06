# cloudforge — "Validated Under Stress" Contract

**Epic:** FXL-STRESS-1 (Break cloudforge before expanding it) · **Milestone:** STRESS
**Status:** authoritative — every stress ticket (STRESS-2…STRESS-12) asserts against these clauses.

This is the machine-checkable definition of *hardened*. It extends FXL-D003 (the 12-point
"validated" definition for a single scenario) to **hostile inputs, scale, and the corpus
pipeline**. FXL-D003 answers "is this one generated scenario internally consistent?"; this
contract answers "can the tool be made to lie, deploy, leak, lose ground truth, emit invalid
artifacts, or export unsafe/restricted data — under adversarial or high-volume input?"

A build **passes stress** only if ALL 15 clauses hold. Each clause names the guard that
enforces it and the ticket(s) that adversarially exercise it.

## The 15 clauses

| # | Clause | Enforced by | Stressed by |
|---|--------|-------------|-------------|
| S1 | No generated scenario is **deployable**. | `models/scenario.py` `deployable` field validator (`_must_not_be_deployable`) | STRESS-2, STRESS-9 |
| S2 | No generated artifact **requires cloud credentials**. | dummy account `000000000000`; `providers.tf` skips creds; no apply path exists | STRESS-3, STRESS-8 |
| S3 | No generated Terraform contains **unsafe interpolation** (`${`/`%{` from user-controlled fields) or **duplicate resource labels**. | `hcl.neutralize_hcl_openers` (FXL-D005); `label_collisions.check_label_collisions` pre-emission (FXL-D006) | STRESS-3 |
| S4 | No graph can claim a **critical path** unless that path is **actually connected**. | `graph_risk` ground-truth-path + `_check_critical_path_connectivity` BFS (FXL-D008) | STRESS-2, STRESS-8 |
| S5 | No **expected finding** references a **missing resource**. | `graph_risk` finding-resource reconciliation | STRESS-2, STRESS-8 |
| S6 | No **broad grant** exists without a **documented expected finding**. | `graph_risk` "broad grants documented" check; `ALLOWED_BROAD_PATTERNS` | STRESS-2 |
| S7 | No **destructive permission** survives validation. | `FORBIDDEN_PERMISSION_PATTERNS` scanned by `graph_risk`, `learn/validate`, and `scenario.rego` | STRESS-2, STRESS-3, STRESS-6 |
| S8 | No **unsafe-operational text** enters the training export — ever, including under `--include-restricted`. | `learn/_safety.is_unsafe_content`; `export.is_exportable` checks unsafe FIRST | STRESS-7 |
| S9 | No **restricted / metadata_only / unknown** source enters the training export **by default**. | `RiskPattern.training_eligible`; `NON_TRAINING_REUSE`; registry loader forces `allowed_for_training=false` | STRESS-6, STRESS-7 |
| S10 | Same input **and seed** produce **byte-identical output**. | deterministic generator/emitter; `random.Random(seed)`, no wall-clock/PID/global RNG | STRESS-4 |
| S11 | **Different seeds preserve risk invariants** (critical path, findings, no forbidden perms). | `MutationGenerator` mutates only cosmetic fields | STRESS-4 |
| S12 | **Scanner scoring is stable** across malformed, partial, empty, and unexpected scanner output — never crashes, never hides missed/unexpected findings. | `validate/scanner_score.py` (fail-soft parse) | STRESS-5 |
| S13 | Optional external tools (`terraform`/`checkov`/`opa`) **fail-soft ONLY when absent or environmentally blocked**. | `tool_probe.detect_tool`; `external_scans` env-error classification (WARN) | STRESS-3, STRESS-6, STRESS-13(CI) |
| S14 | Tool **syntax/config failures fail HARD** (a real terraform syntax error or OPA `deny` is a FAIL, not a WARN). | `external_scans` non-env error → FAIL; OPA deny → FAIL | STRESS-6, STRESS-8 |
| S15 | Reports **cannot render false success** when validation failed — a report never claims PASS for a scenario that FAILed validation. | `report/` renders from artifacts + validation outcomes; no success without pass | STRESS-8, STRESS-9 |

## What "a real bug" means (the fail-and-fix gate)

A stress ticket that produces a **failing test which reproduces a genuine contract violation
in shipped code** has found a real bug. Per the epic rule: write a minimal reproducer, fix the
guard, add regression coverage, re-run. A stress test that fails because the *test* is wrong
(over-strict, mis-modeled input) is a test bug — fix the test.

**Not a bug** (expected defended behavior, must still be asserted):
- A hostile input **rejected with a clear error** (e.g. an S3 name > 63 chars, a non-CIDR block,
  a forbidden permission) — rejection IS the guarantee.
- A hostile HCL value **safely neutralized** so `terraform validate` stays clean.
- A restricted/metadata_only source **excluded** from export.
- An optional tool **absent** → WARN (S13), as long as a tool *syntax* error still FAILs (S14).

## Severity of a violation

| Class | Examples | Response |
|-------|----------|----------|
| **Critical** | S1 deployable slips through; S8 unsafe text exported; S3 live `${}` in emitted HCL; S15 false-success report | stop, reproduce, fix before any further stress work |
| **High** | S4 disconnected critical path passes; S5/S6/S7 integrity gap; S9 restricted export by default | reproduce, fix, regression |
| **Medium** | S12 scorer crash on malformed input; S13/S14 fail-soft misclassification | reproduce, fix, regression |
| **Low** | unclear error message on bad CLI input; missing manifest field | fix opportunistically |

## Acceptance for the epic

The repo is "hardened / ready for the next product phase" when: all 15 clauses have adversarial
coverage that passes; every real bug found has a merged fix + regression test; the stress report
(STRESS-12) enumerates what was tried, what broke, what was fixed, and any residual weak points.
