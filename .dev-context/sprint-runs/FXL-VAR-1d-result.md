# Sprint Result: FXL-VAR-1d
**Status**: SUCCESS
**PR**: #139
**Branch**: feat/FXL-VAR-1d-variation-models
**Files Changed**: 8 (7 new + 1 shared-constant export in mutation_ops.py)
**Tests Added**: 30 variation unit tests (24 initial + 6 from the review-fix regression guard)
**Validation**: ruff=PASS mypy(--strict app/cloudforge/variation/)=PASS pytest=PASS (1815 passed, 99% cov) ai-code-review=PASS(opus, 2 cycles)
**CI**: lint-and-type-check=PASS · Fast(unit/security/property)=PASS · External tools(terraform/checkov/opa)=PASS · mergeStateStatus=CLEAN

## Public API (contract for FXL-VAR-1e)
- `app.cloudforge.variation.models`:
  - `VariationSpec(families: list[str], seed_start: int = 0, seed_count: int, scale_profiles: list[str], variation_axes: dict[str, list[str]] = {}, constraints: VariationConstraints, validation_profile: ValidationProfile)`
  - `VariationConstraints(no_apply: bool = True, no_credentials: bool = True, max_failures_before_abort: int = 25)` — validators reject `no_apply=False`/`no_credentials=False` (structural safety)
  - `ValidationProfile(run_validate, run_report, run_terraform_validate, run_checkov, run_opa)`
  - `RunManifest(run_id: str, entries: list[ScenarioManifestEntry] = [])`
  - `ScenarioManifestEntry(scenario_id, family, seed, scale, axes: dict[str,str], artifact_dir, gen_duration_sec, validation_status, scanner_status, failure_id: str|None)`
- `app.cloudforge.variation.diversity`:
  - `shape_signature(bundle: ScenarioBundle, family: str) -> str` — names/tags excluded; invariant to the mutation engine's benign Subnet injection
  - `diversity_report(bundles: list[tuple[str, ScenarioBundle]], axes: list[str] | None = None) -> dict[str, object]`
  - re-exports `has_decoys`, `has_false_positives`, `has_compensating_controls`
- `app.cloudforge.generate.mutation_ops.EXTRA_SUBNET_ID` — now public (single source of truth for the benign-additive node id)
- `examples/variation/aws_smoke.yaml` — the smoke VariationSpec fixture

## Review gate (AI_REVIEW_GATE, fresh-context Opus)
- **Cycle 1 → FAIL**: caught **P1 (F1)** correctness bug — `shape_signature` broke the central AC
  "cosmetic mutation → same signature" for `public_data_exposure` (the mutation engine injects a benign
  Subnet the base family lacks; the `_count_bucket(0)→_count_bucket(1)` transition flipped the hash).
  Reproduced independently: 10/10 `public_data_exposure` mutations flipped; the shipped tests masked it
  by only exercising `ci_cd_iam_chain`. Plus **P2 (F2)** test-coverage gap.
- **Fix (commit f5a0d81)**: canonicalize the mutation's one documented benign node (`EXTRA_SUBNET_ID`) +
  its originating edge out of the signature; add a parametrized both-families × 3-seed mutation-invariance
  regression test. Verified: mutation flips 10/20 → 0/20; scale/family discrimination preserved.
- **Cycle 2 → PASS**: reviewer confirmed F1/F2 resolved (and validated the new test is a real regression
  guard, not a tautology — it fails against pre-fix code). 0 P1/P2, 2 non-blocking P3.

## Deferred
- **P3 (F3)** — `has_false_positives` couples to the free-text `"benign"` sentinel (correct today; a proper
  fix touches producer modules outside this ticket's scope). Filed as follow-up **#140**.

## Notes / environment
- 2 `test_stress_hcl_corpus` terraform tests failed on first local run due to **disk exhaustion**
  (stale `pytest-of-*` terraform-init scratch, "no space left on device"); reproduced on clean master,
  passed after reclaiming ~16 GB. Not code-related; CI (fresh env) green.
- Local `pre-commit --all-files` has a pre-existing repo-wide mypy failure (flavors/ scaffold +
  .claude/skills/ + Typer-decorator false positives) that reproduces on clean master and touches no
  product files; CI's scoped `mypy app/` passes. Logged to patterns.md.

**Blockers**: none. Ready to merge; merging unblocks FXL-VAR-1e (imports this module).
