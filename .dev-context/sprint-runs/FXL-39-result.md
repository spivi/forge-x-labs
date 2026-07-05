# FXL-39 — Result

- **Status**: DONE (PR open, AI-review APPROVED, CI green, NOT merged)
- **PR**: #42 — https://github.com/spivi/forge-x-labs/pull/42 (mergeStateStatus=CLEAN, mergeable=MERGEABLE)
- **Branch**: `fix/FXL-39-emitter-id-tags` (based on origin/master)
- **Commits** (signed-off):
  - `8af237e` fix(FXL-39): sanitize node.id at resource-label position + total derive_common_tags
  - `cb3a670` refactor(FXL-39): extract resource_name into identifiers.py (module <=200 lines)

## AI review gate

APPROVE — reviewer probed 47 hostile ids + a real terraform breakout attempt, all inert.
One required cleanup applied post-review (below). Two findings explicitly OUT OF SCOPE and
left untouched: the `a-b`/`a_b` sanitize-collision (not reachable from product input,
tracked for a future ticket).

## Post-review cleanup — module-length rule (Option A)

`terraform_resource_blocks.py` had grown to **212 lines**, over the project's documented
"Max 200 lines per module" rule (`.dev-context/rules/general.md`; ruff does not enforce
module length, so CI was clean). Took **Option A**: extracted `resource_name` + its two
regex constants (`_ILLEGAL_ID_CHAR`, `_LEADING_DIGIT`) into a new module
`app/cloudforge/pipeline/identifiers.py`, and re-exported `resource_name` from
`terraform_resource_blocks.py` (`__all__`) so every call site is unchanged. Behavior is
byte-for-byte identical; `resource_name` logic, `derive_common_tags`, and all tests are
unchanged.

- `wc -l` after cleanup: `terraform_resource_blocks.py` = **193**, `identifiers.py` = **32**
  (both ≤200). New module at 100% coverage.
- Re-verified full gate: ruff clean (48 files), mypy --strict clean (36 files), pytest
  **81 passed / 96.27% coverage**; both-family e2e still validate (terraform validate PASS,
  no forbidden permissions, tags pde=prod / ci_cd=staging). CI on PR #42 green
  (lint-and-type-check pass, test pass, 0 failures).

## Files changed (3)

- `app/cloudforge/pipeline/terraform_resource_blocks.py` — `resource_name` now sanitizes any `node.id`
  to a Terraform-legal identifier: `re.sub([^A-Za-z0-9_] -> _)`, then prefixes `_` if empty or
  digit-leading. Output always matches `^[A-Za-z_][A-Za-z0-9_]*$`. Added `import re` +
  `_ILLEGAL_ID_CHAR` / `_LEADING_DIGIT` compiled patterns (no magic literals). `hcl_str` untouched.
- `app/cloudforge/pipeline/terraform_blocks.py` — `derive_common_tags` guards the empty node list
  before `nodes[0]`, returning `NodeTags(env="unknown", owner="unknown", app="unknown")`
  (`_UNKNOWN_TAG` constant); docstring corrected to match. No behavior change for non-empty graphs.
- `tests/cloudforge/test_terraform_emitter.py` — 6 new tests (see below).

## Tests added (6, all pass)

1. `test_resource_name_is_always_a_legal_identifier` — regex-conformance over hostile ids
   `'a" { evil }'`, `'123start'`, `''`, `'x\ny'`, `'a b-c'`, `'a" { evil }" {'` — every output
   matches `^[A-Za-z_][A-Za-z0-9_]*$`.
2. `test_resource_name_maps_hyphen_to_underscore` — benign regression (`deploy-role-1` -> `deploy_role_1`).
3. `test_hostile_id_does_not_inject_new_block` — hostile-id bucket added to the ci_cd graph;
   asserts exactly 3 `aws_s3_bucket` blocks (no injected extra block), emitted label is the
   sanitized identifier `a____evil______injected`, not the raw payload.
4. `test_hostile_id_hcl_is_terraform_valid` — hostile id with `"`/`{`/`}`/newline runs real
   `terraform validate` on the emitted tree -> Success.
5. `test_derive_common_tags_on_empty_graph_does_not_raise` — `derive_common_tags([])` returns
   `NodeTags(env/owner/app="unknown")`, no `IndexError`.

## Validation (all pass)

- **ruff check + format** (`app/ tests/cloudforge/`): All checks passed, 47 files unchanged.
- **mypy --strict app/**: Success, no issues in 35 source files.
- **pytest tests/cloudforge/ --cov=app**: 81 passed; total coverage 96.25% (>= 80). Both changed
  files at 100%. terraform_resource_blocks.py 100%, terraform_blocks.py 100%.
- **hostile-id test**: PASS — `resource_name` regex-conformant over all 6 hostile ids; no injected
  block; `terraform validate` Success on hostile-id tree.
- **empty-tags test**: PASS — `derive_common_tags([])` returns a `NodeTags`, does not raise.
- **CLI e2e both families** (`generate` + `validate` via `PYTHONPATH=. .venv/bin/python -m app.cli`):
  - public_data_exposure: `[PASS] terraform validate`, `[PASS] no forbidden permissions`,
    `main.tf` env=`prod`.
  - ci_cd_iam_chain: `[PASS] terraform validate`, `[PASS] no forbidden permissions`,
    `main.tf` env=`staging`.
  - Existing hcl_str interpolation/breakout tests still pass (part of the 81).
- **CI (PR #42)**: `lint-and-type-check` pass, `test` pass — 0 failures. mergeStateStatus=CLEAN,
  mergeable=MERGEABLE.

## Blockers

None. PR left OPEN (not merged) per instructions.
