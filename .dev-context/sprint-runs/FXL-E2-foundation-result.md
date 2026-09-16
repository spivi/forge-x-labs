# FXL-E2 Foundation — Result

**Status**: ✅ Complete — AI review gate APPROVED, required cleanup applied, CI green, NOT merged (per directive).
**PR**: [#80](https://github.com/spivi/forge-x-labs/pull/80) — `feat/FXL-E2-foundation` → `master`
**Commits**: `204c9e7` (foundation) + `8de0701` (post-review refactor) — both signed-off + Co-Authored-By.
**Tickets closed by this PR**: #61, #62, #58

## AI review gate + post-review cleanup

The AI review gate returned **APPROVE** (governance verified leak-free: 216 input
combinations, 0 leak paths, reproduced independently; registry loader + malformed-input
rejection clean; models correct; scope clean). One required cleanup was applied:

- **Module-length cap (rules/general.md, max 200 lines)**: `pattern_models.py` was 203
  lines. Extracted the RiskPattern-side enums (`CloudProvider`, `Domain`, `WeaknessFamily`,
  `SafetyClassification`, `ValidationStatus`) + the derived `TRAINABLE_CLASSIFICATIONS`
  constant into a new **`app/cloudforge/learn/pattern_enums.py`**; `pattern_models` imports
  and re-exports them (via `__all__`), so every ontology name stays importable from
  `pattern_models` too. **Pure mechanical extraction** — no model logic, field, or the
  `training_eligible` derivation changed (verified: enums are the same objects from both
  modules).
- **Line counts now**: `pattern_models.py` = **142**, `pattern_enums.py` = **92** (both ≤200).
- Re-verified after the refactor: `ruff` + `mypy --strict` clean; both new modules 100%
  covered; **167 passing**, project coverage **96.50%**. training_eligible truth-table +
  registry tests still all pass. CI green (4× SUCCESS), mergeStateStatus CLEAN.

## What was built (foundation only — the dependency root of the epic)

Ontology models + source-registry model/loader + package skeleton. **Nothing fetches or
ingests** — fetch/adapters/normalizer/dedup/quality/corpus/export/CLI are stub homes for
later tickets. No ML, no crawling, no creds, no exploit content.

### Files created — REAL content
- `app/cloudforge/learn/__init__.py` — package docstring.
- `app/cloudforge/learn/pattern_enums.py` (#61, added in post-review refactor) — the
  RiskPattern-side enums `CloudProvider`/`Domain`/`WeaknessFamily`/`SafetyClassification`/
  `ValidationStatus` + `TRAINABLE_CLASSIFICATIONS`.
- `app/cloudforge/learn/pattern_models.py` (#61) — imports/re-exports the enums from
  `pattern_enums`; `PatternProvenance` (all §7 fields, `datetime` timestamps passed in),
  `RiskPattern` (all §6 fields; `graph_fragment` is a real `ScenarioGraph`;
  `expected_findings`/`severity` reuse the findings model; provenance required),
  `RawPatternRecord` (§8 adapter-output shape). `training_eligible` is a derived
  `computed_field`.
- `app/cloudforge/learn/source_models.py` (#58) — `SourceType`/`ReuseStatus` enums,
  `SourceEntry` (url XOR path validator), `SourceRegistry` (`by_id`/`enabled_entries`,
  unique-id validator), `RawCacheMetadata`.
- `app/cloudforge/learn/registry.py` (#58) — `load_registry()` + governance, `RegistryError`
  (`CloudforgeError` subclass), `get_entry`/`enabled_sources` helpers.
- `app/cloudforge/learn/adapters/__init__.py` + `adapters/base.py` — the real `PatternAdapter`
  Protocol (`extract(source, raw_path) -> list[RawPatternRecord]`).

### Files created — STUBS (docstring + `from __future__ import annotations` + `# Implemented in ticket #NN`)
`cli.py` (#15), `fetch.py` (#2), `normalizer.py` (#8), `validate.py` (#9), `dedup.py` (#10),
`quality.py` (#11), `corpus.py` (#12), `export.py` (#13), `summarize.py` (#15),
`adapters/cloudforge_scenario.py` (#6), `adapters/rule_catalog_yaml.py` (#5),
`adapters/checkov_policy_index.py` (#7).

### Tests created (`tests/cloudforge/learn/`)
`conftest.py` (real-model builders), `test_pattern_models.py`, `test_registry.py`,
`test_source_models.py`, `test_package_skeleton.py`. **51 learn tests, all passing.**

## load_registry parses the real registry ✅

`load_registry("data/source_registry.yaml")` loads the actual committed file without error
and governance is verified against real entries:
- `csa-ccm` → `reuse_status=mappings_only`, `allowed_for_training=True` (**FXL-D007 honored**).
- `checkov-terraform-index` → `metadata_only`, `allowed_for_training=False`.
- `cis-benchmarks` → `license=unknown` forced `allowed_for_training=False`.
- `local-rule-catalog` → `full_reuse`, `allowed_for_training=True`.

**FXL-D007 mappings_only handling**: governance forces `False` only for
`{unknown-license, restricted, metadata_only}`; `mappings_only` is left as-declared, so CCM
control-ID mappings remain training-eligible. Mirrored in both the loader (`registry.py`) and
the derived `training_eligible` (`pattern_models.py`, via `NON_TRAINING_REUSE`).

## training_eligible truth-table test — result: ALL PASS ✅

| Inputs | Expected | Result |
|---|---|---|
| valid + defensive + full_reuse + allowed | true | ✅ |
| mappings_only + allowed + benchmark (FXL-D007) | true | ✅ |
| restricted | false | ✅ |
| metadata_only | false | ✅ |
| unknown reuse | false | ✅ |
| unsafe_operational | false | ✅ |
| unvalidated | false | ✅ |
| full_reuse but allowed_for_training=false | false | ✅ |

## Coverage
- New `app/cloudforge/learn/` package: **100%** (real modules + stub imports all covered).
- Full `app` suite: **149 passed**, project coverage **95.55%** (gate ≥80% ✅).

## CI status
PR #80 — `state=OPEN`, `mergeable=MERGEABLE`, `mergeStateStatus=CLEAN`.
All checks green: `lint-and-type-check` pass, `test` pass (statusCheckRollup: 4× SUCCESS).
`ruff check` + `mypy --strict` clean on `app/` + `tests/`. Pre-commit passed (no `--no-verify`).

## Blockers
None. PR is open and clean, awaiting human review. **Not merged** per directive.
