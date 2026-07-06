# FXL-90 — checkov adapter `_parse_rows`: robust to a leading index column

**Status**: Ready
**Priority**: P2
**Type**: fix
**Effort**: S
**Milestone**: E2 — Cloud Risk Pattern Learning Corpus
**Maps to**: GitHub issue #90

## Problem

`CheckovPolicyIndexAdapter._parse_rows` (`app/cloudforge/learn/adapters/checkov_policy_index.py`)
parses the **recorded fixture** HTML correctly (12 records) but extracts **0 records** from the
**real live** Checkov Terraform policy-index page, because the live table has an **extra leading
row-index column** the fixture lacks. The adapter reads the check ID at a **fixed position**
(`row[0]`), but on the live page it is at `row[1]`. Fetch, cache, and content-hash all work — this
is a parse-robustness gap only, surfaced by FXL-74's opt-in `-m internet` test (which skips-with-
reason rather than fails). The metadata-only governance is unaffected (`checkov` is `metadata_only`
/ not training-eligible), so this is **not a leak** — but the adapter is effectively non-functional
against real data, blocking any future use of Checkov as a real source.

## Goal

Make `_parse_rows` robust to a leading index column so it extracts the same records from BOTH the
fixture layout and the live layout, and lock the live shape into the fixture so a unit test guards
against regression.

## Approach

- Detect the **check-ID column by content** — match `CKV_[A-Z0-9]+_\d+` (Checkov's check-ID
  pattern; keep the exact regex in `constants.py` or module-level, no magic literal) — rather than
  reading a fixed column index. Resolve the ID column once per table (or per row, defensively), then
  read the remaining fields relative to it.
- **Update the recorded fixture** (`tests/cloudforge/learn/fixtures/…checkov…html` — locate it) to
  match the **live** table shape (add the leading index column), so the existing fixture-based unit
  test exercises the real-world layout and would have caught this.
- Keep the adapter fail-soft: a row with no `CKV_…` cell is skipped (not a crash), preserving the
  existing "malformed row → skip, never abort" posture.

## Non-Goals

- No change to fetch/cache/hash, the provenance stamping, or the `metadata_only` governance.
- Not adding new fields or changing `RawPatternRecord` shape — same records, correct extraction.
- Not promoting `checkov` to training-eligible (it stays `metadata_only` per the registry).

## Acceptance Criteria

- [ ] `_parse_rows` extracts the same record set from both the old fixed-position fixture shape AND
      the live shape (leading index column) — column detection is content-based, not positional.
- [ ] The recorded fixture is updated to the live table shape; the existing fixture unit test passes
      against it and asserts ≥1 (ideally the full set of) records with correct check IDs.
- [ ] A regression unit test covers the leading-index-column layout explicitly (no internet).
- [ ] The opt-in `-m internet` adapter-extraction test now extracts ≥1 record from the live page
      (still opt-in; not in the default suite).
- [ ] ruff (0.9.4) + mypy --strict clean; bare `pytest tests/cloudforge/ -q --no-cov` green.

## Affected Files

- `app/cloudforge/learn/adapters/checkov_policy_index.py` (`_parse_rows` + a check-ID regex constant)
- `tests/cloudforge/learn/fixtures/…checkov…html` (update to the live shape)
- `tests/cloudforge/learn/test_checkov_policy_index*.py` (regression test for the leading column)

## Threat Model (advisory)

No new attack surface. The adapter parses untrusted remote HTML, but the fix only changes column
selection (content-match on a fixed regex) — it does not execute, eval, or trust the content beyond
extracting text into a `metadata_only` record that is excluded from training export. Input validation
posture is unchanged (fail-soft skip on malformed rows). **Risk neutral / slightly reduced** (the
content-based detection is less brittle than fixed-position parsing).

## Dependencies

Independent. Verifying the live path needs network (the `-m internet` test), but the unit fix +
fixture update are fully offline.
