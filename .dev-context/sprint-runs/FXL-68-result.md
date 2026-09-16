# Sprint Result: FXL-68

**Status**: SUCCESS
**PR**: #91 (https://github.com/spivi/forge-x-labs/pull/91) — NOT merged
**Branch**: feat/FXL-68-dedup
**Files Changed**: 2  **Tests Added**: 12
**Validation**: ruff=PASS mypy=PASS pytest=PASS (dedup.py coverage=100%, overall app=97.49%)
**Blockers**: none

## What shipped

Deterministic corpus dedup per design §9.3, implemented in
`app/cloudforge/learn/dedup.py` (was a stub — `# Implemented in ticket #10`).

- `dedup(patterns: list[RiskPattern]) -> tuple[list[RiskPattern], DedupReport]` —
  groups patterns by the exact dedup key, keeps one survivor per group, returns
  `(survivors, report)`.
- `DedupReport` (new Pydantic model, `extra="forbid"`) — `survivor_ids`,
  `dropped_duplicate_ids` (survivor id -> dropped ids), `groups` (stringified key ->
  `[survivor_id, *sorted(dropped_ids)]`).
- `tests/cloudforge/learn/test_dedup.py` (new) — 12 tests, built on the shared
  `build_pattern()` fixture helper from `tests/cloudforge/learn/conftest.py` via
  `model_copy` to vary key fields.

## Dedup key (design §9.3, verbatim)

```python
key = (
    cloud_provider,
    weakness_family,
    tuple(sorted(affected_resource_types)),
    tuple(sorted(risky_relationships)),
    tuple(sorted(missing_controls)),
    tuple(sorted(compensating_controls)),
)
```

Exact equality only — no fuzzy matching, no embeddings (per the guiding directive
and design §9.3's explicit ML non-goal).

## Collision handling

- **Survivor selection**: `max(group, key=lambda p: (p.quality_score, p.id))`.
  Highest `quality_score` wins; ties (including the common case pre-#69 where every
  pattern still has the default `quality_score=0.0`) break deterministically on
  `id` (lexicographically largest — documented in the docstring/tests).
- **Provenance/duplicate recording**: `RiskPattern` has no dedicated
  "duplicate provenance" or "duplicate ids" field, and the ticket explicitly
  forbade adding one. Chose to:
  - merge dropped duplicates' `source_mappings` into the survivor
    (`source_mappings` is already a "mappings from other sources" bag on the
    model — the natural existing home, and the ticket names this as the
    documented fallback);
  - record dropped ids in the separate `DedupReport.dropped_duplicate_ids`
    (survivor id -> sorted dropped ids) rather than mutating `RiskPattern` at all.
  - `RiskPattern` itself is otherwise untouched — no new fields, no schema change.

## Determinism (shuffle test)

`test_dedup_is_deterministic_regardless_of_input_order` builds a 5-pattern corpus
(2-way collision, 3-way collision via a separate pair, 2 distinct-key patterns),
runs `dedup()` once as baseline, then shuffles the same list with a seeded
`random.Random(1234)` 5 times and re-runs `dedup()` each time — asserting the
survivor id list AND the full `DedupReport` are byte-identical to baseline on
every shuffle. Also covered: empty input, single-pattern input, 3-way collision
(all dropped ids + all `source_mappings` merged), and key-field list-order
insensitivity (sorted tuples absorb permutations of e.g.
`affected_resource_types`).

## Acceptance criteria — all met

- [x] `dedup(patterns) -> (survivors, report)` — groups by the exact §9.3 key,
      keeps highest `quality_score` (id tie-break), records dropped
      `duplicate_ids` + merged `source_mappings`, returns a `DedupReport`.
- [x] Deterministic under shuffle (see above).
- [x] No fuzzy matching / embeddings — exact key tuple equality only.
- [x] Two patterns identical except `quality_score` -> higher survives, lower's
      id recorded as a duplicate (`test_higher_quality_score_survives`,
      `test_identical_except_quality_score_higher_survives_lower_recorded_as_duplicate`).
- [x] Two patterns with different keys -> both kept
      (`test_two_patterns_with_different_keys_are_both_kept`).
- [x] `ruff` (0.9.4) + `mypy --strict` clean; coverage ≥ 80% (`dedup.py` = 100%,
      app overall = 97.49%). Module is 110 lines (≤200); every function ≤30
      lines and ≤3 params (`DedupReport`/`RiskPattern` used instead of wider
      signatures where more data was needed).

## Validation detail

- `ruff check app/cloudforge/learn/dedup.py tests/cloudforge/learn/test_dedup.py --fix` — clean
- `ruff format app/cloudforge/learn/dedup.py tests/cloudforge/learn/test_dedup.py` — unchanged
- `mypy --strict app/cloudforge/` — 57 source files, no issues
- `PYTHONPATH=. .venv/bin/pytest tests/cloudforge/learn/test_dedup.py -q --no-cov` — 12 passed
- `PYTHONPATH=. .venv/bin/pytest tests/cloudforge/ -q --no-cov` — 279 passed, 9 deselected (no regressions)
- `PYTHONPATH=. .venv/bin/pytest tests/cloudforge/ -q --cov=app --cov-report=term-missing` — 97.49% overall, `dedup.py` 100%
- CI on PR #91 — polled 3x via `gh pr checks 91 --watch`; 0 failures across all polls (18 passed, then 8, then 4 remaining — draining to green). No red checks observed.

## Scope discipline

Touched only `app/cloudforge/learn/dedup.py` + its new test file. Did not modify
`pattern_models.py`, `normalizer.py`, or any other `learn/` module. Did not
implement `validate.py`/`quality.py`/`corpus.py`/`export.py`/CLI wiring (all
remain their pre-existing stubs). No `RiskPattern` fields added. PR was not
merged — left open for review per instructions.
