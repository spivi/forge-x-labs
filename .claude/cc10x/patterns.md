<!-- cc10x session memory: PATTERNS. DO NOT DELETE.
     Cross-session knowledge base — gotchas, traps, and learnings that must
     survive compaction and outlive any single ticket. This is the gem: append
     a one-line entry whenever a non-obvious failure or fix is discovered, under
     the right taxonomy heading. Keep entries short and concrete (what + why).
     The session-start hook surfaces this file so future sessions don't relearn
     the same lesson. -->

# Patterns & Gotchas

> Append under the matching heading. Format: `- <symptom/context>: <fix/rule> (why)`.
> Add new headings as the project grows.

## Runtime / Language

## Async & Concurrency

## Testing
- cloudforge product tests live in `tests/cloudforge/` (own conftest with a `generated_scenario` fixture that runs the real generator into `tmp_path`). Force optional tools absent via `monkeypatch.setattr(tool_probe, "detect_tool", lambda name: False)` for deterministic fail-soft tests; mock `external_scans.tool_probe.run_tool` (returning `ToolRun`) to exercise terraform/opa branches without real tools.
- importlib-loaded module with a `@dataclass` + `from __future__ import annotations`: register it in `sys.modules[name]` BEFORE `spec.loader.exec_module` or dataclass field resolution crashes (`dataclasses._is_type` does `sys.modules.get(cls.__module__).__dict__` → None). See `tests/scripts/test_ledger_append.py`.
- scripts/ tests load modules by path (`spec_from_file_location`); a script that imports a sibling (e.g. `dataset` → `debrief`) must `sys.path.insert(0, str(_HERE))` at top so the sibling import resolves under any load context.
- mypy is scoped to `app/` only (`exclude: ^(scripts/|tests/|lemmings/)` in pre-commit); coverage gate is `app/` too. scripts/ is ruff-gated, NOT mypy/coverage-gated — don't chase strict-typing debt there.

## Silent Failures
<!-- The error class that fails quietly instead of raising: dict.get() masking
     invalid input, unguarded float()/int() on external data, parsers deriving
     success from a count, substring matches with false positives. -->

## Performance

## Shell / Cross-platform

## Database / ORM

## Tooling & Build
- `/debrief` correlates `estimates.csv` (planned) with `cost-ledger.csv` `duration_sec` (actual). Directly-spawned background Task agents (not via full `/sprint execute`) do NOT get ledger rows — backfill with `scripts/ledger_append.py --ticket X --result-json <file>` (JSON: `{model, duration_ms, usage:{input_tokens,output_tokens,...}}`) AND mark the ticket done via `tracker.py status set X done`, or debrief sees 0 runs. Calibration needs `min_samples=3` per type/effort bucket — 2 tickets → "not enough samples" (correct, not a bug).
- `lemmings fit` emits `cost_rate_per_min` via internal normalization, NOT `total_cost/total_minutes` — the raw knob is not hand-reproducible from the ledger. Don't claim a derivation you can't reproduce.
- The council doc-write hook (`council-on-doc-write.sh`, `COUNCIL_REVIEW=on`) fires AUTOMATICALLY when you Write a `*_summary.md`/`*_report.md`/plan/`*_evr.md` — you'll see an `auto:<name>` row in `kpis/council.csv`. No need to invoke `council-review.sh` manually for those (running it again just adds a second row). Members: codex + agy (both need subscription CLI auth on PATH); chair Sonnet.
- Product package is `app/cloudforge/` (NOT `src/`): CI hardcodes `--cov=app` + `mypy app/` and the console script is `cloudforge = "app.cli:app"`. `app/cli.py` re-exports the real Typer app from `app/cloudforge/cli.py`. Poetry needs `packages = [{include = "app"}]` (project name `cloudforge` ≠ package dir `app`). See FXL-D001.
- Ruff `TCH`/`TC` was REMOVED from `select`: it pushes type-only imports into `if TYPE_CHECKING:` blocks, which breaks Pydantic v2 (`model_validate` needs field-type imports importable at runtime). Enable the `pydantic.mypy` plugin so mypy understands `Field(alias="from")` + `populate_by_name`; add `types-pyyaml` for yaml stubs.
- `GraphEdge` uses `from_: str = Field(alias="from")` (`from` is a keyword). Serialize graph.json with `model_dump(by_alias=True)`; the OPA rego + risk engine read the `from` key.
- Local python is 3.14 but project targets `^3.12`/mypy `3.12`: create the venv with `poetry env use 3.12` for typecheck parity.
- CSV schema migration that must stay back-compat: `store._columns()` reads the FILE's live header on write, so old-width files round-trip until a `migrate` command rewrites them with the canonical `COLUMNS`. Migrators must be idempotent (`if _columns(p) == COLUMNS: return False`) and back-fill new typed columns from the legacy `labels` string.
- `budgets.yml` pricing must carry FAMILY keys (`opus`/`sonnet`/`haiku`) for the version-proof family-first lookup in `ledger_append`/`billing_costs`, AND the version-pinned keys (`claude-opus-4-6`) the SessionEnd bash hook matches exactly. Keep both.
- New `rules/*.md` must be registered in `sync-tool-configs.py::CURSOR_RULE_CONFIG` then `--sync`'d, else the pre-commit drift hook (`--check`) fails. Generated `.cursor/.antigravity` files are untracked (only `.gitkeep` tracked) — regenerate, don't commit.
- **Mechanical validation passing ≠ semantically correct.** FXL-96 auto-built graph fragments that passed `validate_fragment` (endpoints resolve, known types, quality score) while encoding FALSE cloud semantics (`IAMPolicy -can_read-> IAMRole`; a fabricated DataSet forced into an IAM scenario). Only an ADVERSARIAL MEANING review caught it. For any data whose VALUE is its correctness (a training/benchmark corpus), the review gate must judge SEMANTICS, not just structure — and the reviewer should EXECUTE the pipeline to recompute claimed counts, not trust the author's report or the test constants. FXL-98 fixed it by hand-authoring 14 real fragments + tests that assert the exact false shapes are ABSENT (no IAMPolicy edge actor; DataSet only in real data-sink seeds; kms→IAMPolicy not silently Application).
- **Reuse the computed field, don't re-derive the gate.** The FXL-71 export gate is `pattern.training_eligible AND quality_score >= 0.70` — `training_eligible` (a `RiskPattern` computed_field) already encodes validation+safety+reuse+FXL-D007. Re-deriving those checks in the exporter would be a second source of truth that can drift. An absolute-exclusion check (`unsafe_operational`) must be ordered FIRST, before any opt-in relaxation branch (`--include-restricted`), so it structurally cannot be bypassed.
- **`.venv` can get committed as a tracked symlink (mode 120000)** by a worktree-cleanup `ln -sfn` mishap, despite being gitignored — it then shows as `D .venv` in every worktree and re-adds itself in PR diffs cut from before the cleanup. `git rm --cached .venv` + commit; rebase in-flight branches onto the cleanup so they drop the re-add. Re-establish the worktree symlink (`ln -sfn "$(pwd)/.venv" <worktree>/.venv`) after a rebase that dropped the tracked entry.
- **Structural diversity = fragment composition.** Cosmetic diversity (`MutationGenerator` names/tags/one extra subnet) must never count toward `shape_signature`. The diversity gate is the depth bar; a 0-FAIL suite that misses it is `cosmetic variation only`, not success.
- **FXL-VAR-1g `evaluate_gate` consumes the live `diversity_report.json`** (suite-level metrics, percents 0–100). Do not implement the Task 14 stub's fictional `per_family` 0–1 shape — `--gate` would then disagree with the file the suite runner writes.

## Last Updated
_2026-09-16 — FXL-VAR-1h: variation docs + structural-vs-cosmetic diversity lesson._
