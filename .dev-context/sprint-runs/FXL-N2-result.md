# FXL-N2 — Adversarial graph-field corpus — Result

**Status**: DONE (PR open, CI green, not merged) · **PR**: [#51](https://github.com/spivi/forge-x-labs/pull/51) — Closes #45
**Branch**: `fix/FXL-N2-adversarial-corpus` (rebased on `origin/master` incl. merged FXL-N1)
**Date**: 2026-07-05 · **Tier**: fix (P1) · **AI review**: APPROVE + 2 non-blocking nits (both closed, cycle 1)

## Summary

Established a dedicated `tests/security/` regression corpus that applies every hostile
graph-field value to every untrusted HCL string sink, locking in the FXL-35 (`${}`/`%{}`
interpolation) and FXL-39 (`node.id` → resource label) emitter hardening under **real
`terraform validate`** (terraform v1.5.7 on PATH — run, not skipped).

**A NEW bypass WAS found: YES — two of them.** The corpus is not just a lock-in; running
it against every sink under real terraform revealed two live emitter defects the prior
hardening missed. Both are now fixed (minimal, in `terraform_resource_blocks.py`).

## Newly-found defects (fixed in this PR)

### 1. `jsonencode(...)` arguments are LIVE HCL strings (interpolation bypass)
Untrusted IAM `resource` / `actions` and the bucket-policy `Resource` (which embeds
`node.name`) were serialized with `json.dumps` and wrapped in `jsonencode(...)`. HCL
evaluates `${}`/`%{}` inside the JSON string handed to `jsonencode`, so those values were
in a **live interpolation context**, NOT inert. The old `hcl_str` docstring even claimed
"JSON policy documents built via `json.dumps` are already inert" — this was false.

Proven with real terraform:
- IAM `resource = "${data.nonexistent.thing.value}"` → **`terraform validate` FAILED**
  ("Reference to undeclared resource").
- IAM `resource = "%{ for x in [1,2] }${x}%{ endfor }"` → `terraform console` **silently
  evaluated it to `12`** (semantics hidden — exactly the threat FXL-N2 targets).

**Fix**: extracted `neutralize_hcl_openers` (the `${`→`$${`, `%{`→`%%{` step, previously
inline in `hcl_str`) and applied it at the JSON policy sinks (`_actions`, `_resource_arn`,
and the bucket-policy `Resource` arn) — not only in `hcl_str`.

### 2. Astral-plane characters break terraform (surrogate-escape bypass)
`json.dumps` defaults to `ensure_ascii=True`, escaping non-BMP characters (e.g. the emoji
`😀`) as a UTF-16 **surrogate pair** `😀`. HCL cannot decode `\uD800`–`\uDFFF`
("Cannot encode character U+d83d in UTF-8") → **`terraform validate`/`init` FAILED** for
any `name`/`cidr`/`ingress_cidr` carrying an emoji.

**Fix**: `json.dumps(..., ensure_ascii=False)` in `hcl_str` and the policy documents. The
`.tf` files are UTF-8, so raw UTF-8 is valid HCL; `"` / `\` / control chars stay escaped.
BMP unicode (`café`, `日本`, Cyrillic look-alikes) was already fine via `\uXXXX`.

Both defects and the fix rationale are recorded in **DECISIONS.md → FXL-D005**.

## Files

- `tests/security/__init__.py` — package marker
- `tests/security/conftest.py` — the shared `HOSTILE_VALUES` corpus (single source) +
  `hostile`/`corpus` fixtures. 26 entries covering: interpolation/template openers,
  quote/brace/resource breakouts, path traversal, whitespace/control (newline/tab/null-byte),
  unicode confusables (café/日本/emoji/Cyrillic), 256-char label, empty, null-like
  (`null`/`None`/`~`), and Terraform keywords (`provider`/`resource`/`variable`/`locals`).
- `tests/security/test_hcl_injection_corpus.py` — corpus × every HCL string-value sink
  (name → role/policy/sg/bucket, tag values → common_tags, IAM resource arn, cidr,
  ingress_cidr, **bucket-policy arn** — the third jsonencode sink, see nit 1 below).
  Per-value inertness (no live `${`/`%{`, no quote breakout, no raw newline)
  + real `terraform validate` over the whole corpus in a schema-free `locals` block + an
  end-to-end interpolation-payload validate + an isolated bucket-policy-document validate.
  Includes a terraform-verified `_has_live_hcl_opener` helper (a lone `$`/`%` before `{`
  is live; `$$`/`%%`+ is literal).
- `tests/security/test_identifier_sanitization_corpus.py` — corpus × `node.id`; asserts
  `resource_name` output always matches `^[A-Za-z_][A-Za-z0-9_]*$`, no breakout chars, no
  injected `resource` block, and a bounded real `terraform validate`.
- `app/cloudforge/pipeline/terraform_resource_blocks.py` — the two-defect fix (minimal):
  `neutralize_hcl_openers` extracted + applied at JSON policy sinks; `ensure_ascii=False`.
- `.dev-context/DECISIONS.md` — FXL-D005.

## Acceptance criteria

- [x] Every corpus value on every string sink is EITHER inert under real
  `terraform validate` OR rejected with a clear validation error. (After the fix, all
  HCL-injection surfaces are inert; AWS provider content-schema rejections — S3 bucket
  name > 63 chars, IAM role name charset, non-CIDR `cidr_block` — are the legitimate
  "OR rejected" branch, distinct from a breakout, and the corpus terraform test isolates
  the pure HCL-injection surface from provider naming rules.)
- [x] FXL-35 (`${}`/`%{}`) and FXL-39 (`node.id` label) surfaces regression-locked.
- [x] `tests/security/` exists and runs in the suite; ruff + mypy --strict clean.

## Review cycle 1 — both non-blocking nits closed

**Nit 1 (third jsonencode sink regression-lock).** The corpus exercised the IAM
`resource`/`actions` jsonencode sinks but not `_bucket_policy_block` (which embeds
`node.name` into a jsonencode policy arn) — the neutralize call there was correct but
UNTESTED. Added two tests, parametrized over the same corpus:
- `test_sink_bucket_policy_arn` — forces `_bucket_policy_block` to emit via
  `compensating_control="true"`, asserts block-level inertness for every hostile value.
- `test_bucket_policy_document_interpolation_is_inert_under_terraform` — isolates the
  emitted jsonencode document into a schema-free `locals` and validates under real terraform.
**Discrimination proven**: with `neutralize_hcl_openers` temporarily removed from the
bucket-policy sink, both fail — the 4 interpolation-class corpus rows on the block-level
test, and the terraform test with the real "Reference to undeclared resource `nonexistent`"
error. Fix restored; both green.

**Nit 2 (CI lint blind spot).** Extended the two CI lint steps in `.github/workflows/ci.yml`
(`ruff check` + `ruff format --check`) to cover `tests/security/` alongside
`app/ tests/cloudforge/`. mypy stays `app/`-only (fine). The new folder is now a
first-class CI citizen.

## Validation results (post-nits, post-rebase)

- **Local full suite**: `746 passed`, coverage **95.56%** (gate 80%);
  `terraform_resource_blocks.py` at **100%**. `tests/security/` = 424 tests, all green,
  with real terraform v1.5.7. Both scenario families (`ci_cd_iam_chain`,
  `public_data_exposure`) `terraform validate` exit 0.
- **ruff** `check` + `format --check` clean on `app/ tests/cloudforge/ tests/security/`.
- **`mypy --strict app/`** clean (37 files, incl. N1); `mypy --strict tests/security/` clean.
- **CI (PR #51)**: `lint-and-type-check` PASS, `test` PASS (`746 passed` — confirms the new
  bucket-policy tests are collected). `mergeStateStatus: CLEAN`, `mergeable: MERGEABLE`.
  Terraform-gated tests skip in CI (no terraform there); verified against real terraform locally.

## Notes / blockers

- **Rebase**: rebased cleanly onto `origin/master` (FXL-N1 scanner-scorer merged — disjoint
  files: N1 = `validate/scanner_score.py` + report; N2 = emitter + `tests/security/`). No
  conflicts. Full gate re-run green after rebase.
- **Ruff version drift (flagged for follow-up, not fixed here — out of scope)**: CI installs
  UNPINNED ruff (currently 0.15.20) while the local `.venv` pins ruff **0.8.6** and
  `.pre-commit-config.yaml` pins **0.9.4**. 0.8.x vs 0.9+ disagree on assert-with-message
  wrapping. This first surfaced when nit 2 put `tests/security/` under CI's ruff. Resolved
  for this PR by formatting those files to the CI/pre-commit (0.9.4/0.15.20) style
  (whitespace-only `style(FXL-N2)` commit). **Recommend**: pin CI ruff to match the venv/
  pre-commit version (or bump the venv to 0.9.4) so local and CI formatting never diverge.
- **Module length**: `terraform_resource_blocks.py` is 199 lines (under the 200-line rule).
- **Transient**: one full-suite run hit a `no space left on device` during a terraform-init
  (local disk 100% full from accumulated `.terraform` provider downloads); cleaned up, all
  green thereafter — environmental, not a code/test defect (per DECISIONS gate #8).
- No merge performed (per instructions). PR is green + CLEAN and awaits merge.
- Duplicate logical-id / AWS-name collision (mentioned in #45) is explicitly the FXL-N4
  surface; this corpus keeps sanitization labels distinct (unique stems) so it stays a pure
  sanitization test, not a collision test.
