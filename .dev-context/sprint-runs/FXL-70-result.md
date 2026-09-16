# Sprint Result: FXL-70

**Status**: SUCCESS
**PR**: #95 (https://github.com/spivi/forge-x-labs/pull/95) — NOT merged
**Branch**: feat/FXL-70-corpus-validate
**Files Changed**: 3  **Tests Added**: 33
**Validation**: ruff=PASS mypy=PASS pytest=PASS (corpus.py + _corpus_checks.py coverage=100%, overall app=97.56%)
**Blockers**: none

## What shipped

Corpus load/save + the design §9.5 corpus-level validation gate, implemented in
`app/cloudforge/learn/corpus.py` (was a stub — `# Implemented in ticket #12`),
mirroring the FXL-D003 12-point scenario discipline applied to the whole corpus.

- `load_corpus(path) -> list[RiskPattern]` — reads JSONL, `model_validate`s each
  non-blank line. `training_eligible` (a `computed_field`, not settable) is popped
  off the payload first — `model_validate` would otherwise reject it as an unknown
  field (`extra="forbid"` on `RiskPattern`). A malformed line (bad JSON, non-object,
  or schema-invalid `RiskPattern`) raises `CorpusLoadError` naming the file and line
  number.
- `save_corpus(patterns, path)` — writes one `model_dump(mode="json")` per line,
  `sort_keys=True`, creating parent dirs as needed. Deterministic (identical input →
  identical bytes on repeated writes) and lossless (every settable field round-trips
  unchanged).
- `validate_corpus(patterns) -> CorpusValidationReport` — runs every §9.5 check,
  returns `pattern_count` + itemized `issues: list[CorpusIssue]` (`pattern_id`,
  `check`, `message`) and a `.passed` property.
- New private module `app/cloudforge/learn/_corpus_checks.py` — per-pattern checks,
  split out to keep both files under the 200-line module cap.

## Checks (design §9.5) + reuse of `validate_fragment`

- **Provenance completeness** (`provenance_complete`) — every `PatternProvenance`
  string field (except `notes`) must be non-blank. "No provenance, no corpus."
- **Fragment validity** (`fragment_valid`) — **reuses**
  `app.cloudforge.learn.validate.validate_fragment` +
  `validate.validation_reasons` directly; no fragment-validation logic was
  reinvented in `corpus.py`/`_corpus_checks.py`.
- **Unique id** (`unique_id`) — no two patterns may share an `id`; all colliding ids
  reported once per corpus.
- **No unsafe_operational** (`no_unsafe_operational`) — any pattern with
  `safety_classification == unsafe_operational` fails (they must have been rejected
  upstream by the normalizer/validator).
- **training_eligible consistency** (`training_eligible_consistent`) — recomputes
  the design §6/FXL-D007 eligibility rule (`validation_status == valid AND
  safety_classification in {defensive_pattern, benchmark_pattern, training_pattern}
  AND provenance.allowed_for_training AND provenance.reuse_status not in
  {restricted, metadata_only, unknown}`) independently from the pattern's own
  fields and compares it against the stored `training_eligible`. Since
  `training_eligible` is a `computed_field` (a pure `@property`), a normally
  constructed `RiskPattern` can never disagree with itself — the check earns its
  keep by comparing field **values** rather than enum identity, which catches a
  pattern that reached the corpus via a bypassed validator (e.g. `model_construct`),
  where an enum-typed field can hold a bare `str` that no longer compares equal
  (`is`) to the enum member the real property checks against, silently flipping
  `training_eligible` without the stored data *looking* wrong.
- **Enums in-vocabulary** — enforced by Pydantic itself at `load_corpus` time (any
  out-of-vocabulary value fails `model_validate` and surfaces as a clear
  `CorpusLoadError`), documented explicitly rather than re-implemented.

## JSONL round-trip confirmation

`TestLoadSaveRoundTrip` + `TestRealCorpusEndToEnd.test_clean_real_corpus_round_trips_losslessly_through_jsonl`:
save → load reproduces `model_dump(mode="json")` byte-for-byte equal to the original
for both hand-built patterns and the full real 13-pattern deduped corpus; order is
preserved; repeated `save_corpus` calls on the same input produce identical bytes.

## Real end-to-end test corpus (seeds → normalize → validate → dedup)

`_real_corpus()` helper loads the real 14-entry `data/rule_catalog/seed_patterns.yaml`
via the registry + `RuleCatalogYamlAdapter`, runs it through `PatternNormalizer` +
`validate_fragment`, then `dedup()` (13 survivors — one real collision). This real
corpus:
- normalizes/validates cleanly (`test_fourteen_seeds_normalize_and_dedup_to_a_real_corpus`)
- passes `validate_corpus` with zero issues (`test_clean_real_corpus_passes_validate_corpus`)
- round-trips losslessly through JSONL (above)

## Violations tested (each crafted individually + asserted caught)

- **Duplicate id**: two/three patterns sharing an id → `unique_id` issue, reported
  once per corpus even on a 3-way collision.
- **Missing/incomplete provenance**: blank `source_id`, blank/whitespace-only
  `adapter_name` → `provenance_complete` issue naming the blank field(s); blank
  `notes` explicitly allowed (not a required field).
- **Fragment fails validation**: a policy node granting `iam:DeleteRole` (forbidden
  destructive action, rule 4) and a finding referencing a missing node (rule 3) →
  `fragment_valid` issue carrying the same reason text `validate.validation_reasons`
  produces (proving reuse, not reimplementation).
- **unsafe_operational present**: pattern with `safety_classification =
  unsafe_operational` → `no_unsafe_operational` issue; every other classification
  confirmed to NOT trigger this check.
- **training_eligible inconsistent**: a `model_construct`-built pattern with
  `validation_status` stored as the bare string `"valid"` (real
  `PatternProvenance`/other fields untouched) recomputes `training_eligible=False`
  live (the latent bug) while the eligibility rule recomputed from the same fields
  says `expected=True` → `training_eligible_consistent` issue with both values in
  the message. Also confirmed: consistent `True` and consistent `False` cases both
  pass cleanly.
- **Multiple simultaneous violations**: a 4-pattern corpus mixing duplicate ids +
  missing provenance + `unsafe_operational` → all three `check` types present in one
  report.

## Acceptance criteria — all met

- [x] `load_corpus`/`save_corpus` round-trip a list of `RiskPattern`s via JSONL
      losslessly + deterministically; malformed JSONL → clear `CorpusLoadError`
      (a `CloudforgeError`).
- [x] `validate_corpus(patterns) -> report` enforces all §9.5 checks; the clean real
      seeds→normalize→validate→dedup corpus passes; every violation listed above is
      detected with a clear itemized issue.
- [x] Reuses `validate.validate_fragment` (`_fragment_issues` calls it directly plus
      `validation_reasons` for the message detail) — no reinvented fragment
      validation.
- [x] `ruff` (0.9.4) + `mypy --strict` clean; coverage ≥80% (`corpus.py` +
      `_corpus_checks.py` both 100%; whole-`app` 97.56%). Modules: `corpus.py` 142
      lines, `_corpus_checks.py` 117 lines (both ≤200); every function ≤30 lines;
      wider data needs satisfied via `RiskPattern`/tuple returns instead of >3-param
      signatures.

## Validation detail

- `ruff check app/ tests/ --fix` — all checks passed
- `ruff format app/ tests/` — 114 files unchanged
- `PYTHONPATH=. .venv/bin/mypy --strict app/` — 60 source files, no issues
- `PYTHONPATH=. .venv/bin/pytest tests/cloudforge/learn/test_corpus.py -q --no-cov` — 33 passed
- `PYTHONPATH=. .venv/bin/pytest tests/cloudforge/ -q --no-cov` — 333 passed, 9 deselected (no regressions)
- `PYTHONPATH=. .venv/bin/pytest tests/cloudforge/ -q` (with coverage) — 97.56% overall;
  `corpus.py` 61/61 (100%), `_corpus_checks.py` 46/46 (100%)
- CI on PR #95 — polled via `gh pr checks 95 --watch` (3x); 0 failures across all
  polls (15→9 pending draining to 4 remaining, then all green). No red checks
  observed.

## Scope discipline

Touched only `app/cloudforge/learn/corpus.py` + new `_corpus_checks.py` (private
split, same ticket's scope) + `tests/cloudforge/learn/test_corpus.py`. Did not modify
`pattern_models.py`, `normalizer.py`, `validate.py`, or `dedup.py` — read and reused
only (`validate_fragment`/`validation_reasons` imported, not reimplemented). Did not
touch `quality.py` (ticket #69, running in parallel) or `export.py`/`cli.py` (later
tickets, still their pre-existing stubs). No `--no-verify` used at any point. PR left
open, not merged, per instructions.
