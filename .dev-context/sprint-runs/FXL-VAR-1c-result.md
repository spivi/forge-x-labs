# Sprint Result: FXL-VAR-1c
**Status**: SUCCESS
**PR**: #138 (https://github.com/spivi/forge-x-labs/pull/138)
**Branch**: feat/FXL-VAR-1c-graph-composer

GraphComposer engine (Tasks 6–8 of epic FXL-VAR-1): a seeded fragment-composition
engine behind the existing `ScenarioGenerator` protocol, an integrity regression
net, and a `--engine composer --seed N` CLI option. Tasks 1–5 (fragments + scale
profiles) were already merged via tickets 1a/1b.

## Acceptance Criteria
- [x] **Determinism — same `(spec, seed)` → BYTE-IDENTICAL graph/findings/ground_truth.**
  Only randomness is `Random(seed)` driving the fragment plan. Verified by
  `test_composer.py::test_same_seed_byte_identical` + 10 parametrized
  `test_composer_integrity.py::test_composed_scenarios_are_deterministic` cases +
  `test_cli_composer.py::test_composer_engine_is_deterministic` (byte-compares graph.json).
- [x] **Globally-unique node ids; collision RAISES `GraphIntegrityError` (existing class).**
  Per-instance ns (`decoy0/…`, `noise3/…`); `_assert_unique_ids` runs before projection.
  Verified by `test_node_ids_unique_across_fragments` + `test_id_collision_raises_graph_integrity_error`.
- [x] **Scale profile fills the node band (medium → 75–150; respects shipped min/max).**
  `_fill_to_scale` appends benign_noise to `>= min_nodes`, never exceeding `max_nodes`;
  extras clamped under the ceiling. Verified across all 5 profiles × both families × 15 seeds;
  tests: `test_scale_profile_fills_node_band`, `test_small_profile_fills_node_band`,
  `test_stays_within_max_nodes_for_tiny_profile`.
- [x] **Integrity net: families × seeds {0,1,2,17,99} → ZERO validation FAIL.**
  `test_composer_integrity.py` writes each scenario via `ScenarioArtifacts.write_all` and runs
  the full `run_validations` (schema + graph-risk + terraform validate + checkov + OPA).
  20/20 pass (526s local; CI "External tools" job green). Net surfaced + fixed 2 real budget bugs.
- [x] **`--engine template` (default) UNCHANGED; `--engine composer` writes a valid tree.**
  Default stays template, byte-identical to before (`test_default_engine_still_template`,
  `test_explicit_template_engine_matches_default`). Composer writes a full valid tree
  (`test_generate_composer_engine`). Unknown engine → clean `error:` + exit 1 via existing
  `_CLI_ERRORS` (`test_unknown_engine_is_clean_error`).

## Files Changed
- `app/cloudforge/generate/composer.py` (new, 150 lines) — `GraphComposer` + `ComposerGenerator`
- `app/cloudforge/cli.py` — `--engine`/`--seed` options + `_build_bundle` dispatch
- `app/cloudforge/errors.py` — `UnknownEngineError` (CloudforgeError subclass)
- `app/cloudforge/validate/graph_risk.py` — scale-aware `_effective_budget`
- `policies/scenario.rego` + `policies/scenario_test.rego` — resource ceiling 40→500
- `tests/cloudforge/test_opa_policy.py` — budget test updated to new boundary
- `tests/unit/generate/test_composer.py` (new, 15 tests)
- `tests/integration/test_composer_integrity.py` (new, 2 parametrized → 20 cases)
- `tests/integration/test_cli_composer.py` (new, 5 tests)

## Tests
- Added: 22 test functions (composer unit 15 + integrity 2×[2 fam × 5 seed]=20 + cli 5).
- Full suite (CI): **1776 passed, 13 skipped** (up from 1749 baseline).
- Coverage (CI): **98.98%** total (gate ≥85%); composer.py 100%.
- mypy --strict app/cloudforge/generate/: clean (via `.venv/bin/mypy`).

## Verifier
```
PYTHONPATH=. .venv/bin/pytest tests/unit/generate/test_composer.py \
  tests/integration/test_composer_integrity.py tests/integration/test_cli_composer.py -q --no-cov
  → 40 passed in 446.24s (0:07:26)     [20 unit + 5 cli(15 collected) + 20 integrity]
.venv/bin/mypy --strict app/cloudforge/generate/  → Success: no issues found in 19 source files
```
(The verifier's bare `mypy` resolves to the homebrew system binary lacking the pydantic
plugin — a pre-existing poetry-env quirk; the correct/CI invocation `.venv/bin/mypy` is clean.)

CI checks on PR #138: all 6 green (lint-and-type-check ×2, Test: Fast ×2, Test: External tools ×2);
mergeStateStatus CLEAN, mergeable MERGEABLE.

## Notes / Blockers
- **Integrity net found 2 real budget bugs (fixed at source, not by weakening the test):**
  Scale profiles legitimately exceed the example specs' `max_resources` (30/40) and the OPA
  rego's hardcoded `40`. (1) graph-risk budget is now scale-aware:
  `max(constraints.max_resources, scale_profile.max_nodes)` — a composer scenario may fill its
  scale band without a spurious over-budget FAIL, while a runaway graph is still caught.
  (2) OPA rego resource ceiling raised 40→500 (largest deployable tier `large`); OPA can't read
  the per-scenario spec, so it's a coarse ceiling — the tight per-scenario budget stays enforced
  by the Python graph-risk engine. (3) Composer clamps mandatory extras under `max_nodes`.
- **mypy invocation nuance:** the verifier writes bare `mypy`, but in this worktree `mypy`
  resolves to the homebrew system binary which lacks the pydantic plugin (pre-existing env quirk;
  see patterns.md "poetry env use 3.12 for typecheck parity"). The correct/CI invocation is
  `.venv/bin/mypy --strict app/cloudforge/generate/` → clean. CI `lint-and-type-check` is green.
- Did NOT merge (per instructions) — sprint orchestrator handles merge ordering.
- No AI review comments were posted on the PR at report time.
