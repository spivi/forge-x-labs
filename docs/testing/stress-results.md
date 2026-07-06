# cloudforge — Stress-Test Results (FXL-STRESS-1)

**Epic:** FXL-STRESS-1 — "Break cloudforge before expanding it" · **Milestone:** STRESS
**Completed:** 2026-07-06 · **Verdict:** ✅ **GO** for the next product phase (with two documented residual notes)

The epic's mandate was to prove `cloudforge` cannot **lie, deploy, leak, generate invalid
artifacts, silently lose ground truth, or export unsafe/restricted corpus data** — under hostile
input, scale, and malformed external-tool output. Twelve tickets across nine surfaces, each
asserting against the 15-clause contract ([`stress-contract.md`](stress-contract.md)).

**Headline:** 7 real bugs found and fixed — every one in the validation / report / policy / CLI
**integrity layer**, none discoverable from feature work. The two "no bug" results were the ones
most aggressively attacked. The test suite grew **889 → 1,746 tests**.

## Bug ledger

Every bug was captured first as a `strict=True` xfail with a minimal reproducer (fast suite stayed
green, nothing hidden), then fixed in-PR and flipped to a passing regression. Each fix passed a
fresh-context Opus review that independently executed the exploit before approving.

| # | Bug | Severity | Clause | Found by | Fix | PR |
|---|-----|----------|--------|----------|-----|-----|
| 1 | **Report rendered false success** — `report.md` presented a scenario's critical path as fact even when `validate` FAILed it (no validation section at all) | 🔴 Critical | S15 | differential (STRESS-8) | `report` runs `run_local_validations` + a `## Validation` section with a FAIL banner; broken paths flagged NOT VERIFIED | #120 |
| 2 | **Path traversal** — `SourceEntry.path` read verbatim; `../../etc/passwd` resolved through at ingestion | 🟠 High | (traversal) | corpus adversarial (STRESS-7) | load-time `SourceEntry` validator + resolve-time `is_relative_to` containment (defense in depth) | #119 |
| 3 | **Phantom-resource findings** — `graph_risk` never checked `ExpectedFinding.resource_ids` reference real nodes | 🟠 High | S5 | property-based (STRESS-2) | new `_check_finding_resources_exist` in the graph engine | #121 |
| 4 | **Scanner not-scored ambiguity** — "scanner never ran" and "checkov.json corrupt" printed identically, hiding a scoring failure | 🟡 Medium | S12 | scanner-score (STRESS-5) | `not_scored_reason` diagnostic + `warnings[]` surfaced as caveats | #123 |
| 5 | **OPA missed `no_real_secrets`** — the policy had zero secret enforcement; a node with a real AWS/PEM secret produced no denials | 🟡 Medium | S7 | OPA tests (STRESS-6) | coarse, family-agnostic secret-scan deny rule (superset of `_safety.py`) | #125 |
| 6 | **`deployable: true` leaked a raw traceback** — `generate` caught only `CloudforgeError`, not the `ValidationError` the guard raises | 🟡 Medium | S1 | CLI (STRESS-9) | scoped `_CLI_ERRORS = (CloudforgeError, ValidationError, OSError)` on every command | #126 |
| 7 | **Read-only `--out` leaked a raw `OSError`** — same catch gap | 🟡 Medium | S1/S15 | CLI (STRESS-9) | same `_CLI_ERRORS` fix | #126 |

**Severity note:** #1 is the only Critical — the guarantee *itself* failed (a broken scenario
presented as valid). #6/#7 are Medium, not Critical: the guarantee **held** (the scenario was still
rejected), the defect was raw-traceback UX. That distinction matters for a benchmark tool whose
value is trust — a report that lies is categorically worse than a CLI that fails ungracefully.

## The two clean results (verified, not assumed)

A "no bug" result on a security surface is only trustworthy if someone tried hard to break it:

- **Mutation determinism (STRESS-4):** 2,000 variants (2 families × 1,000 seeds) — **0
  nondeterminism, 0 path-loss, 0 forbidden-perm hits, 0 cosmetic collisions.** S10/S11 solid.
- **HCL injection (STRESS-3):** 108 hostile values × every string sink — emitter held. The reviewer
  **monkeypatched the neutralizer to a no-op to prove the tests aren't vacuous**, then ran 22 of its
  own novel injections (jsonencode sibling-key, `${${x}}`, heredocs, NUL, unicode-RTL) through real
  `terraform 1.5.7`. All inert. S2/S3/S7 hold.
- **Performance (STRESS-10):** generate/validate/report + dedup/quality/export all **flat per-item**
  from 100 → 10,000 scenarios / 100 → 100,000 patterns. No O(N²), no unbounded memory.

## Contract-clause coverage

| Clause | Guarantee | Status |
|--------|-----------|--------|
| S1 | No deployable scenario | ✅ enforced + CLI now fails cleanly (#126) |
| S2 | No cloud credentials required | ✅ verified (HCL corpus, no apply path) |
| S3 | No unsafe interpolation / duplicate labels | ✅ 108-value corpus + real terraform (#124) |
| S4 | Critical path must be connected | ✅ property-based + the FXL-79 BFS check |
| S5 | Findings reference real resources | ✅ **fixed** (#121) |
| S6 | Broad grants documented | ✅ property-based (STRESS-2) |
| S7 | No destructive permission survives | ✅ engine + rego (secrets gap **fixed** #125) |
| S8 | Unsafe text never exported | ✅ 46 adversarial cases, gate held (STRESS-7) |
| S9 | Restricted/metadata_only not exported by default | ✅ gate held; `--include-restricted` never admits unsafe |
| S10 | Same seed → byte-identical | ✅ 2,000-variant sweep (STRESS-4) |
| S11 | Different seeds preserve risk | ✅ 2,000-variant sweep (STRESS-4) |
| S12 | Scanner scoring stable on malformed output | ✅ 15 fixtures, never crashes/hides (fix #123) |
| S13 | Optional tools fail-soft when absent | ✅ opa/checkov/terraform skip-with-reason |
| S14 | Tool syntax/config failures fail hard | ✅ opa deny → FAIL, terraform syntax → FAIL |
| S15 | Reports cannot fake success | ✅ **fixed** (#120) — the epic's marquee fix |

**All 15 clauses have adversarial coverage that passes.**

## Residual weak points (documented, non-blocking)

1. **OPA secret-detection blind spot** — a bare 40-char AWS secret-key *value* under a benignly-named
   key (no `AKIA`/PEM self-describing shape) is not caught by the rego. This exactly mirrors
   `_safety.py` (the rego is a strict superset), and the generators never emit such values. Coarse
   gate; acceptable. Tighten only if a real source starts carrying such data.
2. **CLI catch breadth** — `_CLI_ERRORS` includes `OSError`, which could in principle mask a
   domain-layer defect that raises a bare `OSError` for a non-filesystem reason. Idiomatic for a
   top-level CLI boundary; programming bugs (`KeyError`/`AttributeError`/`TypeError`) still propagate
   (verified). Acceptable trade-off.

Neither blocks the next product phase; both are noted for future hardening.

## Process notes (for the next epic)

- **`.venv` re-staging** recurred (agents `git add`-ing the gitignored symlink). A pre-commit hook
  rejecting a staged `.venv` would make this structural instead of relying on review.
- **Wave rebasing** — running waves against a moving master means later branches go behind; each was
  rebased before merge (clean, disjoint files). Expected cost of parallelism.
- **Disk hygiene** — a terraform-backed test filled the disk via stale tmp trees; later tickets used
  bounded tmp dirs + cleanup. Worth a shared fixture.

## Verdict: GO

`cloudforge` is **hardened and ready for the next product phase.** The stress epic found and fixed
the class of defect that a benchmark/training tool cannot afford — a report that lies, a validator
that misses phantom resources, an ingestion path that reads arbitrary files, a policy blind to
secrets — none of which would have surfaced from adding a third scenario family. All 15 contract
clauses now have passing adversarial coverage; the two residual notes are documented and benign.

The product's differentiator — **trusted, labeled scenarios with hard validation boundaries** — now
rests on demonstrated, adversarially-verified guarantees rather than assumption.
