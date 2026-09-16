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
- **A count-bucketing hash that keeps 0 in its own bucket flips on a benign +1 that introduces a NEW type.** FXL-VAR-1d `shape_signature` bucketed per-type node/edge counts with `_count_bucket(0)=0`, `_count_bucket(1)=1` distinct ("presence matters"). The MutationGenerator injects one benign Subnet + `belongs_to_app` edge; for a base family WITHOUT a Subnet (`public_data_exposure`), that crossed the 0→1 bucket and flipped the "cosmetic mutation → same signature" AC — 10/10 flips. **Tests passed only because they exercised the one family (`ci_cd_iam_chain`) that already had a Subnet.** Lesson: an invariance test must cover EVERY family/base that can trigger the invariant, not the one where it happens to hold — and a signature meant to be invariant to a documented additive delta must canonicalize that exact delta out (id-based, via a shared `mutation_ops.EXTRA_SUBNET_ID` constant), not rely on bucket width. Only an adversarial fresh-context reviewer that RAN the mutation across both families caught it (mirrors the FXL-96 semantic-review lesson: execute the pipeline, don't trust the passing tests).

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
- **Run repo commands through the venv binaries (`.venv/bin/ruff|mypy|pytest`), not the system ones.** In a fresh shell/worktree, bare `ruff`/`mypy` resolve to system installs with different config and no pydantic → false "4 ruff errors" / "No module named 'pydantic'". Always prefix with `.venv/bin/`.
- **`pre-commit run --all-files` has a PRE-EXISTING repo-wide mypy failure** (~20 errors in `flavors/cli/` template scaffold with literal `{{PROJECT_NAME}}`, `.claude/skills/dependency-guard/scripts/`, and Typer-decorator `[misc]` false positives) that reproduces identically on clean `master` and touches ZERO product files. It's config drift between the pre-commit mypy hook (unscoped) and CI's properly-scoped `mypy app/`. CI's own `lint-and-type-check` passes. Do NOT chase it as if a PR introduced it — check whether the flagged files are yours; per-file commit hooks (which pass on staged product files) are the real gate.
- **Terraform-corpus security tests need disk + network:** each `test_stress_hcl_corpus` test does a full `terraform init -backend=false` that downloads the ~700MB `hashicorp/aws` provider into `tmp_path`. Stale `pytest-of-<user>` scratch under `$TMPDIR` accumulates to 10s of GB; on a near-full disk terraform init dies with "no space left on device" and the tests FAIL (looks like a code break, isn't). `rm -rf $TMPDIR/pytest-of-*` to reclaim; the failures vanish. CI runs clean (fresh env). **If the disk fills to 100%, even the Bash tool errors ENOSPC on its own output file** — recover by running `rm -rf $TMPDIR/pytest-of-spivi >/dev/null 2>&1; true` (redirect to /dev/null so the harness output file is ~empty).
- **Integration tests that call `run_validations`/the CLI must force external tools ABSENT** — `monkeypatch.setattr(app.cloudforge.validate.tool_probe, "detect_tool", lambda name: False)` (autouse fixture; the established `tests/integration/test_cli_composer.py` pattern). Otherwise every test shells out to a real ~700MB terraform provider download per scenario. FXL-VAR-1e's suite-runner tests (14 tests × 10 scenarios) exhausted a 460GB disk and ran for minutes before this fix; hermetic → 1.7s, zero disk. terraform-absent is the intended `if_available` config (design §5; ACs "runs without credentials" / "degrades WARN when absent") — CI's dedicated `External tools` job covers terraform-present.
- **A manifest/artifact record storing an ABSOLUTE tmp path breaks a strict determinism assertion** (same content, different `out_dir` → different `artifact_dir` string). FXL-VAR-1e stores `artifact_dir` RELATIVE to the run dir (`scenarios/<id>`, via `rel.as_posix()`); consumers (replay) resolve it against `run_dir`. Determinism is a property of content, not the output location — and the manifest becomes portable. Store paths relative to the run root in any reproducible run tree.
- **`.venv` can get committed as a tracked symlink (mode 120000)** by a worktree-cleanup `ln -sfn` mishap, despite being gitignored — it then shows as `D .venv` in every worktree and re-adds itself in PR diffs cut from before the cleanup. `git rm --cached .venv` + commit; rebase in-flight branches onto the cleanup so they drop the re-add. Re-establish the worktree symlink (`ln -sfn "$(pwd)/.venv" <worktree>/.venv`) after a rebase that dropped the tracked entry.
- **Structural diversity = fragment composition.** Cosmetic diversity (`MutationGenerator` names/tags/one extra subnet) must never count toward `shape_signature`. The diversity gate is the depth bar; a 0-FAIL suite that misses it is `cosmetic variation only`, not success.
- **Platform switch (Grok ↔ Antigravity):** resume from `STATUS.md` **Current State** (Antigravity already loads `.antigravity/rules/general.md`, which requires STATUS.md + DECISIONS.md on start). The v1 plan is `docs/superpowers/plans/2026-09-16-v1-oss-labs.md`. Do not re-open the product decision.
- **FXL-VAR-1g `evaluate_gate` consumes the live `diversity_report.json`** (suite-level metrics, percents 0–100, `unsupported_axes` per family). The VAR-1 implementation-plan Task 14 stub used a fictional `per_family` 0–1 shape — implementing that stub would make `--gate` disagree with the file `suite_runner` writes.
- **Student pack must never leak the answer key.** Strip `security` objects from nodes and edges in `estate.json`; do not mention critical-chain node IDs or `can_pass_role` in `brief.md`. Leak tests (`tests/cloudforge/lab/test_strip.py`) are load-bearing.

## Last Updated
_2026-09-16 — v1 OSS labs complete: all 6 PRs merged, 5 families live, lab/grade verified._
