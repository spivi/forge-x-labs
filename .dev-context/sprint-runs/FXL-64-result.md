# FXL-64 — cloudforge scenario adapter — Result

**Status**: Complete — implemented, tested, CI green, NOT merged (per directive).
**PR**: [#84](https://github.com/spivi/forge-x-labs/pull/84) — `feat/FXL-64-scenario-adapter` → `master`
**Commit**: `b305e71` — `feat(FXL-64): cloudforge scenario adapter` (signed-off)
**Ticket closed by this PR**: #64

## Issue-numbering discrepancy (flag for human reconciliation)

GitHub issue #64's **title** ("cloudforge scenario adapter") and issue #63's **title**
("rule catalog YAML adapter") are swapped relative to their **bodies**: #64's body
describes the `checkov_policy_index` (metadata-only) spec, and #63's body describes
this `cloudforge_scenario` spec verbatim. Confirmed via the pre-existing stub file's
own docstring: `app/cloudforge/learn/adapters/cloudforge_scenario.py` said
`"""(STUB — implemented in ticket #6)"""`, matching #63's body, not #64's.

I built to my assigned task spec (which is unambiguous and matches #63's body and
design §8 exactly), not the mismatched #64 body text. PR #84 closes #64 (the ticket ID
I was assigned), since the tracker's ticket-ID-to-branch mapping (`FXL-64` /
`feat/FXL-64-scenario-adapter`) is what's authoritative for routing this work, even
though the GitHub issue's own title/body pairing is internally inconsistent. A parallel
agent on FXL-63 built the rule_catalog_yaml adapter (correct per its label) — so despite
the swapped bodies, both concrete deliverables ended up correct. Recommend a human fix
the #63/#64 title-vs-body swap in the tracker so future issue reads aren't misleading.

## What was built

Implemented `CloudforgeScenarioAdapter` in the previously-stubbed
`app/cloudforge/learn/adapters/cloudforge_scenario.py` (design §8, adapter 1): ingests
existing `out/<scenario>` dirs (`scenario.yaml` / `graph.json` /
`expected_findings.json` / `ground_truth_paths.json`) — already validated,
self-consistent product outputs — into `RawPatternRecord`s.

### Scenario -> record mapping

For each scenario dir:
1. Load all four artifacts via the **existing** models/loaders — no hand-rolled
   JSON/YAML parsing: `ScenarioSpec.model_validate(load_yaml(...))`,
   `ScenarioGraph.model_validate(load_json(...))`,
   `ExpectedFindings.model_validate(load_json(...))`,
   `GroundTruthPaths.model_validate(load_json(...))`, with paths resolved via
   `ScenarioPaths.from_dir(scenario_dir)`.
2. Select the **most severe ground-truth path** (critical > high > medium > low;
   first path wins ties) — one record per scenario dir, keyed on that path.
3. Map fields:
   - `raw_id` = the path's `id` (e.g. `path-critical-01`)
   - `title` = `f"{scenario.scenario_type} — {path.severity} risk path"`
   - `summary` = the path's `explanation`
   - `cloud_provider` = `scenario.cloud` (`aws`)
   - `resource_types` = sorted, deduped `GraphNode.type` values for every node on
     the path
   - `severity` = the path's severity
   - `category` = `scenario.scenario_type`
   - `remediation` = deduped, space-joined remediations of every
     `ExpectedFinding` whose `resource_ids` overlap the path's nodes
   - `raw_payload` = `{"graph": <json str>, "expected_findings": <json str>,
     "ground_truth_path": <json str>}` (the field is typed
     `dict[str, str | list[str]]`, so nested structures are JSON-serialized strings)
4. Provenance: `adapter_name="cloudforge_scenario"`, `adapter_version="0.1.0"`,
   `extraction_method="scenario_dir"`, `content_hash` = sha256 over the combined
   sorted-key JSON of graph + findings + ground_truth, `confidence=0.85`,
   `source_id`/`source_name`/`source_license`/`reuse_status`/`allowed_for_training`
   passed through from the `SourceEntry` (i.e. `local-scenarios-out`,
   `full_reuse`, `allowed_for_training=true`).

Supports both a single scenario dir (`raw_path` has its own `scenario.yaml`) and a
parent dir containing multiple scenario dirs (each child with its own
`scenario.yaml` is discovered and ingested independently).

### Error handling

Missing `raw_path` or any missing/invalid artifact inside a discovered scenario dir
raises `ScenarioAdapterError` (a `CloudforgeError` subclass) — never an unhandled
crash. An empty parent dir (no scenario children) returns `[]`, not an error.

## Files changed

- `app/cloudforge/learn/adapters/cloudforge_scenario.py` (implemented; was a stub) —
  200 lines
- `tests/cloudforge/learn/adapters/__init__.py` (new package)
- `tests/cloudforge/learn/adapters/test_cloudforge_scenario.py` (new, 8 tests)
- `tests/cloudforge/learn/fixtures/scenario_ci_cd_iam_chain/{scenario.yaml,
  graph.json,expected_findings.json,ground_truth_paths.json}` (real, trimmed
  `cloudforge generate` output — no terraform/, no hand-authored JSON)
- `tests/cloudforge/learn/fixtures/scenario_public_data_exposure/{...}` (same, other
  family)

`app/cloudforge/learn/adapters/__init__.py` was NOT touched (no export needed —
callers instantiate `CloudforgeScenarioAdapter` directly, matching how the
`PatternAdapter` protocol tests use adapters elsewhere in the codebase).

## Test count

**8 new tests** in `test_cloudforge_scenario.py`:
1. `test_extract_ci_cd_iam_chain_maps_critical_path_to_record` — happy path, family 1
2. `test_extract_public_data_exposure_maps_critical_path_to_record` — happy path,
   family 2
3. `test_extract_stamps_complete_provenance` — every provenance field checked
4. `test_extract_parent_dir_ingests_all_child_scenarios` — multi-scenario parent dir
5. `test_extract_missing_scenario_dir_raises_cloudforge_error`
6. `test_extract_incomplete_scenario_dir_raises_cloudforge_error` (has
   `scenario.yaml` only, missing the other three artifacts)
7. `test_extract_empty_parent_dir_returns_no_records`
8. `test_adapter_satisfies_pattern_adapter_protocol`

Fixtures were generated for real via
`PYTHONPATH=. .venv/bin/python -m app.cli generate examples/ci_cd_iam_chain.yaml
--out /tmp/...` and `examples/public_data_exposure.yaml`, then the four JSON/YAML
artifacts (not the `terraform/` dir) were copied into
`tests/cloudforge/learn/fixtures/` — so the adapter is exercised against real
product artifact structure, not hand-authored JSON.

## Validation

- `ruff check --fix` (0.9.4): clean
- `ruff format`: clean
- `mypy --strict app/`: clean (57 source files, 0 issues)
- `pytest tests/cloudforge/ -q --no-cov -m 'not stress'`: **175 passed**
- Full suite `pytest tests/` (repo default, coverage gate active): **818 passed, 5
  deselected** (stress marker), **coverage 96.62%** (gate is 80%)
- Module size: `cloudforge_scenario.py` is exactly 200 lines (rules/general.md cap)
- CI (`gh pr checks 84`): **all green** — `lint-and-type-check` SUCCESS, `test`
  SUCCESS (checked via `gh pr checks --watch`, twice, no failures)
- No `ai-code-review.yml` workflow exists in this repo yet, so the AI review gate
  described in CLAUDE.md did not fire — nothing to wait on there.

## Blockers

None. PR #84 is open, green, mergeable — awaiting human merge decision (per
directive, did not merge). Only outstanding item is the #63/#64 title/body swap in
the issue tracker, noted above and in the PR description, for a human to reconcile.
