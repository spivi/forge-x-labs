# FXL-N1 — Scanner result scorer — Result

- **Status**: Done (PR open, CI green, NOT merged) — AI review fix cycle 1/3 applied (1 BLOCKER + 2 nits resolved)
- **PR**: #50 — https://github.com/spivi/forge-x-labs/pull/50 (Closes #44)
- **Branch**: `feat/FXL-N1-scanner-scorer` (based on origin/master)
- **Milestone/Type**: M7 / feature / P1 — closes gap #10 of the 12-point validated
  definition (FXL-D003): scanner output is scored against expected findings.

## What was built
Maps observed **Checkov** failed-checks to graph-level `expected_findings.json` and
scores coverage, turning cloudforge from a generator into a benchmark harness.

**Modeling challenge solved:** Checkov keys findings by Terraform resource ADDRESS
(`aws_iam_role.role_deploy`); expected findings key by GRAPH NODE id (`role-deploy`).
No 1:1 map. The scorer inverts the emitter's `resource_name` mapping — strip the
`aws_<type>.` prefix to the bare label, then match against `resource_name(node)` for
each graph node. Detected = an expected finding with >=1 checkov failed-check on one
of its `resource_ids`; unexpected = a failed-check touching no expected-finding
resource (observed false positive). Reported honestly (no forced 1:1) — the mismatch
is the useful signal.

## Files
- `app/cloudforge/validate/scanner_score.py` — NEW: scorer + typed `ScannerScore`
  Pydantic model; `score_scenario()` / `write_scanner_score()`; fail-soft (`None` =
  not scored) on missing/unparseable checkov.json.
- `app/cloudforge/validate/orchestrator.py` — writes `scanner_score.json` in `validate`
  (`_score_scanner` step: PASS with coverage detail, or WARN "not scored").
- `app/cloudforge/report/sections.py` + `report/renderer.py` — `## Scanner Score` section
  (matched/missed/unexpected + coverage; "not scored — no scanner output" when absent).
- `app/cloudforge/constants.py` + `io/paths.py` — `scanner_score.json` filename + path.
- `tests/cloudforge/test_scanner_score.py` — NEW (8 tests, mocked checkov fixtures).
- `tests/cloudforge/test_report.py`, `test_validate_orchestrator.py` — +4 wiring tests.
- Read-only (per scope): `identifiers.py`, emitter internals, mutation, other validators.

## Tests
- New: 8 scorer tests + 4 report/orchestrator wiring tests = **12 new**.
  Cover happy path (real-sample numbers), no-checkov (not scored), all-matched,
  all-missed, empty failed_checks, malformed JSON (fail-soft), file write, orchestrator
  PASS+writes-file, report present/absent. All use MOCKED checkov (no real checkov in
  unit tests — deterministic + CI-safe).
- Full suite: **93 passed**, coverage **95.62%** (gate 80%).

## Validation
- `ruff check` + `ruff format`: clean.
- `mypy --strict app/`: clean (37 files).
- `pytest --cov=app`: 93 passed, 95.62%.
- **REAL e2e** (checkov 3.3.0 + opa 1.18.2 installed): `generate → validate → report`
  on `examples/ci_cd_iam_chain.yaml`. Full stack PASS (terraform validate, checkov scan,
  scanner score, opa policy). `scanner_score.json` written; report shows the section.
- CI (PR #50): **4/4 checks green** (lint-and-type-check ×2, test ×2). Zero fix cycles.

## REAL scanner-coverage numbers (ci_cd_iam_chain, live checkov 3.3.0)
```json
{ "scanner": "checkov", "expected_findings": 5, "matched_findings": 4, "missed_findings": 1,
  "unexpected_findings": 0, "expected_detected_count": 4, "expected_missed_count": 1,
  "false_positive_observed_count": 0, "scanner_coverage_score": 0.8 }
```
- **Coverage 0.8 (4/5 detected), 0 false positives.**
- 5 checkov failed-checks landed on 4 distinct nodes: role-deploy, role-runtime, sg-web,
  s3-public-assets — matching the passrole, s3read, sg, and FP findings.
- **Missed: find-logging-01** (s3-customer-exports, trail-main) — checkov has no
  failed-check on those resources. This is exactly the graph-level risk (missing S3
  access logging / CloudTrail data events) that a resource-hygiene scanner cannot see —
  the scorer surfaces it as an honest miss.

## AI review gate — fix cycle 1 of 3 (REQUEST CHANGES → resolved)
Reviewer confirmed the score logic is correct (independently reproduced 0.8 and 0.33;
exact-match mapping, consistent counts, div-by-zero guarded). One real **BLOCKER**: a
reachable fail-soft violation.

- **BLOCKER (fixed): fail-soft contract broken on non-dict `results`.** `score_scenario`
  is documented never to raise, but the try/except in `_load_failed_resources` only
  wrapped `json.loads`. Valid JSON with a non-dict `results` — `{"results": null}`,
  `{"results": 42}`, `{"results": {"failed_checks": null}}` (a truncated/interrupted
  checkov write or a scanner error object) — made the chained `.get` raise
  `AttributeError`, crashing `report.md` rendering (the report path calls
  `score_scenario`). **Fix:** guard the intermediate value — `results` must be a `dict`
  and `failed_checks` a `list` before chaining/iterating; any structurally-unexpected
  shape → `None` ("not scored"), never raises.
  ```python
  results = payload.get("results", {})
  if not isinstance(results, dict):
      return None
  failed = results.get("failed_checks", [])
  if not isinstance(failed, list):
      return None
  ```
- **Nit 1 (fixed):** `orchestrator._score_scanner` `assert score is not None` (stripped
  under `python -O`) → explicit `if score is None: <WARN outcome>`.
- **Nit 2 (fixed):** `_unexpected_count` now dedups unmatched targets by graph node when
  resolvable (consistent with the node-set matched/missed counts); unresolvable addresses
  keyed by address. Headline coverage/matched/missed unchanged.

**New tests** (`test_scanner_score.py`, parametrized over 5 structurally-broken shapes
`{results:null}`, `{results:42}`, `{results:{failed_checks:null}}`, `{results:{failed_checks:7}}`,
`{results:[]}`):
- `test_non_dict_results_is_fail_soft_not_raise` — `score_scenario(...)` returns `None`,
  does not raise.
- `test_render_is_fail_soft_on_structurally_broken_checkov` — `ReportRenderer(dir).render()`
  shows "not scored — no scanner output.", does not raise.

**Re-verified (fix commit `dca79f0`):** ruff + `mypy --strict` clean; `pytest --cov=app`
**103 passed, 95.55%** (>=80%). Manual check confirmed all three malformed cases return
`None` (not raise) and render fail-soft. Real e2e scores **unchanged: ci_cd 0.8, pde 0.33**.
CI on PR #50: **4/4 green**. Pushed (updates PR #50); NOT merged.

## Blockers
None.
