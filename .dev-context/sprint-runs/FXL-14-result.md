# Sprint Result: FXL-14

**Status**: SUCCESS
**PR**: #28
**Branch**: feat/FXL-14-mutation-engine
**Files Changed**: 4  **Tests Added**: 19
**Validation**: ruff=PASS mypy=PASS pytest=PASS (coverage=95.61%)
**Blockers**: none

## What shipped

A seeded, deterministic `MutationGenerator` that produces cosmetic +
benign-additive variants of a base `ScenarioBundle` for scanner-benchmark
diversity, without changing the ground-truth risk.

- `app/cloudforge/generate/mutation_generator.py` (new) — orchestrator taking a
  base bundle + int seed (+ optional `max_resources` for budget safety),
  returning a mutated `ScenarioBundle`. Uses an explicit `random.Random(seed)`
  (no global RNG / wall-clock / PID) → same seed yields byte-identical
  `graph.json`.
- `app/cloudforge/generate/mutation_ops.py` (new) — pure seeded transforms:
  rename display names, jitter tags from fixed benign vocabularies (honours
  `no_real_secrets`), inject one benign unused subnet within budget. Node `id`s,
  edges, ground-truth paths, and expected findings untouched.
- `app/cloudforge/cli.py` (modified, +18/-1) — thin `--mutate-seed N` option on
  `generate`, delegating to `MutationGenerator`.
- `tests/cloudforge/test_mutation_generator.py` (new) — 19 tests.

## Acceptance criteria — all met

- [x] `MutationGenerator(base, seed).generate()` returns a valid `ScenarioBundle`.
- [x] Same seed → byte-identical `graph.json`; different seed → different
      names/tags, identical node `id`s on the ground-truth path.
- [x] `GraphRiskEngine` all-PASS on 4 seeded variants (parametrized 1/7/42/1337).
- [x] No forbidden permission / broad-grant-doc regression.
- [x] `ruff` + `mypy --strict` clean; coverage on `app` = 95.61% (≥ 80%).

## Validation detail

- `ruff check app/ tests/cloudforge/` — clean
- `ruff format --check app/ tests/cloudforge/` — clean
- `mypy --strict app/` and `mypy app/ --ignore-missing-imports` (CI) — clean
- `PYTHONPATH=. pytest tests/ --cov=app` — 273 passed, 95.61% (new modules 100%)
- End-to-end CLI (`generate --mutate-seed 1` → `validate`) — all-PASS, exit 0
- CI on PR #28 — `lint-and-type-check` + `test` both SUCCESS; mergeState CLEAN.
  Passed on first attempt (0 fix cycles).

## Conflict awareness (FXL-26)

`template_generator.py` was NOT touched — the `--mutate-seed` option lives in
`cli.py` (which FXL-26 does not edit). Rebase on `origin/master` after FXL-26
merges should be trivial. No shared files reformatted.

## Notes

- Pre-commit's isolated `mirrors-mypy` hook reports `import-untyped` (yaml) +
  `untyped decorator` (typer) errors because its `additional_dependencies` omit
  `types-PyYAML`/`typer` stubs. This fails identically on **baseline unmodified**
  files (e.g. `io/loaders.py`) and is a pre-existing `.pre-commit-config.yaml`
  gap outside this ticket's scope. The authoritative CI gate
  (`mypy app/ --ignore-missing-imports`) passes, as does `mypy --strict app/` in
  the project venv. No `--no-verify` was used; no git hooks are installed in the
  worktree, so `git commit` was not bypassed.
