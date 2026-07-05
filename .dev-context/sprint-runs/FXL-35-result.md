# FXL-35 Result — Harden Terraform emitter: per-family tags + HCL escaping

- **Status**: DONE (PR open, CI green, NOT merged per instructions)
- **PR**: #38 — https://github.com/spivi/forge-x-labs/pull/38
- **Branch**: `fix/FXL-35-emitter-hardening` (based on origin/master)
- **Files changed**: 4
  - `app/cloudforge/pipeline/terraform_resource_blocks.py` — added `hcl_str()` helper + `_str_attr()`; routed all scalar string values (name/cidr/ingress_cidr/bucket-name) through `hcl_str`
  - `app/cloudforge/pipeline/terraform_blocks.py` — added `derive_common_tags()`; `build_main_tf(tags)` now renders graph-derived tags (escaped)
  - `app/cloudforge/pipeline/terraform_emitter.py` — threads `derive_common_tags(graph)` into `main.tf` (now graph-aware, not static)
  - `tests/cloudforge/test_terraform_emitter.py` — 4 new tests
- **Tests added**: 7 (2 per-family tags: pde→prod, ci_cd→staging; 2 quote/newline-injection; 3 `${}`/`%{}` interpolation — added in fix cycle 1)
- **Commits**: 3, all `--signoff`
  - `bfd44b1` fix(FXL-35): escape all scalar HCL string values via single hcl_str helper
  - `c04783c` fix(FXL-35): derive common_tags from the scenario graph (per-family)
  - `312f553` fix(FXL-35): neutralize HCL `${}` / `%{}` interpolation in hcl_str (review-gate fix)

## Fix Cycle 1 — AI review-gate BLOCKER: `${}` / `%{}` interpolation (RESOLVED)

The review gate (and coordinator) correctly found that `hcl_str = json.dumps(value)`
neutralized `"`/`\`/newline but left HCL's interpolation `${...}` and template-directive
`%{...}` openers live (JSON leaves `$ % { }` verbatim). Every value through `hcl_str` was
therefore still an injection sink.

- **New `hcl_str`**: before `json.dumps`, replace `${` → `$${` and `%{` → `%%{` (HCL's own
  literal-escape sequences) on the raw value; `$`/`%` are JSON-safe so `json.dumps`
  preserves them. Two-layer escaping documented in the docstring.
- **Three reviewer breakout inputs — now confirmed inert (real `terraform validate`)**:
  - `${data.nonexistent.thing.value}` → emitted `$${data.nonexistent.thing.value}` → `terraform validate` **Success** (previously exit 1, "Reference to undeclared resource").
  - `x${local.fake_account_id}` → `x$${local.fake_account_id}` → literal string, no silent local substitution.
  - `%{ for x in [1,2] }${x}%{ endfor }` → `%%{ for x in [1,2] }$${x}%%{ endfor }` → inert, no live template directive.
- **New tests**: `test_interpolation_payload_is_inert`, `test_template_directive_payload_is_inert`,
  `test_interpolation_reference_does_not_break_validate` (the last runs real `terraform init` +
  `terraform validate` on the emitted tree when terraform is on PATH). Existing quote+newline tests kept.
- **Non-blocking nits** (`resource_name` label position, `derive_common_tags` empty-list IndexError):
  NOT touched — coordinator is filing a follow-up; scope held.

## Validation

- **ruff check**: All checks passed (`app/ tests/cloudforge/`)
- **ruff format --check**: 47 files already formatted
- **mypy --strict app/**: Success, no issues (35 source files)
- **pytest tests/cloudforge/ --cov=app**: 76 passed, coverage **96.21%** (≥80 gate met; all three touched pipeline modules at 100%). The interpolation test runs real `terraform init` + `validate` in-test.
- **CLI e2e — both families** (`python -m app.cli generate` + `validate`):
  - `public_data_exposure` → `main.tf` common_tags `env = "prod"` / `app = "customer-data-lake"` / `owner = "data-platform-team"`; CLI validate all-PASS; `terraform validate` **Success**
  - `ci_cd_iam_chain` → `main.tf` common_tags `env = "staging"` / `app = "analytics-exporter"` / `owner = "platform-team"`; CLI validate all-PASS; `terraform validate` **Success**
  - Both: `no forbidden permissions` PASS, `broad grants documented` PASS
- **Injection test** (CALLED OUT): `test_hostile_bucket_name_does_not_inject_new_resource` — a hostile bucket `name` containing `"` + newline + `resource "aws_iam_role" "injected" {…}` does **NOT** create a new HCL block; bucket resource count stays 3 (2 real + 1 hostile); payload survives only inside a single backslash-escaped string literal. Before the fix this test proved the breakout (an `aws_iam_role "injected"` block was emitted); after `hcl_str`, the quote is `\"`-escaped and the newline cannot start a new HCL line. **PASS.**
- **Invariants held**: dummy account id `000000000000` present in tf files; only `mock_access_key`/`mock_secret_key` (no real secrets); no forbidden destructive actions in HCL.

## CI

- PR #38 checks after fix cycle 1: watched to green (see final report)
- Fix-push cycles used: 1 of 3 (AI review-gate BLOCKER on `${}`/`%{}` interpolation)

## Blockers

None. NOT merged (per task instructions — deliver PR only).
