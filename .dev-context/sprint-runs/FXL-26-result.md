# FXL-26 Result — Second scenario family `public_data_exposure`

**Status**: SUCCESS
**PR**: #29 — https://github.com/spivi/forge-x-labs/pull/29
**Branch**: `feat/FXL-26-public-data-exposure` (based on origin/master)
**Files changed**: 5 (2 new source/example/test each net; +330 / -1)
**Tests added**: 9 (in `tests/cloudforge/test_public_data_exposure.py`)

## Files
- `app/cloudforge/generate/public_data_exposure.py` (new, 169 lines) — mirrors `ci_cd_iam_chain.py` (`_node`/`_edge` helpers, `build_graph`/`build_ground_truth`/`build_findings`).
- `app/cloudforge/models/findings.py` — added `FindingFamily.S3_PUBLIC_EXPOSURE` (one member; genuinely needed for the critical direct-exposure finding).
- `app/cloudforge/generate/template_generator.py` — additive: one import + one `_BUILDERS` entry keyed `public_data_exposure`; ci_cd_iam_chain entry untouched (minimal diff for FXL-14 parallel rebase).
- `examples/public_data_exposure.yaml` (new) — valid ScenarioSpec (aws, scenario_type public_data_exposure, deployable false, max_resources 30, 7 nodes).
- `tests/cloudforge/test_public_data_exposure.py` (new).

## Design
Direct data exposure (distinct from the IAM privilege chain). Critical ground-truth path:
`acct-main → (exposed_to_internet) → s3-public-data → (stores_sensitive_data) → data-customer-pii`.
Reuses existing NodeType/EdgeType enums. `s3-locked-backups` = benign false-positive
(`public_looking_bucket_with_compensating_control`); `s3_logging_missing` medium finding on the public bucket.

## Validation
- ruff check + ruff format: PASS (scoped app/ tests/cloudforge/)
- mypy --strict app/: PASS (no issues, 32 files)
- pytest tests/cloudforge/: 44 passed, coverage 95.40% (>=80 gate); new module 100%
- CLI e2e (PYTHONPATH=. .venv/bin/cloudforge): generate → full artifact tree; validate → all-PASS (schema, ground-truth reachable, no forbidden perms, broad grants documented; terraform validate PASS; checkov/opa fail-soft WARN — not installed); report → renders critical path + 3 findings + local-only banner.
- Regression: ci_cd_iam_chain generate/validate/report unchanged (all-PASS).
- CI (PR #29): all checks SUCCESS (lint-and-type-check, test). mergeStateStatus=CLEAN, mergeable=MERGEABLE. NOT merged (per instructions).

## Blockers
None. Fix cycles used: 0 (green on first CI run).

## Note
The installed `cloudforge` console script resolves to the main-repo `app/` package; run the
CLI from the worktree with `PYTHONPATH=.` so it uses the worktree code. Tests already run with
`PYTHONPATH=.` per project convention, so this only affects manual CLI invocation.
