# Sprint Result: FXL-VAR-1f
**Status**: SUCCESS
**PR**: #142
**Branch**: feat/FXL-VAR-1f-variation-cli
**Files Changed**: 4 (new variation/cli.py + test_variation_cli.py; cli.py wiring; replay.py bugfix)
**Tests Added**: 8 integration tests (test_variation_cli.py)
**Validation**: ruff=PASS mypy(--strict app/cloudforge/variation/)=PASS verifier(8 CLI tests)=PASS CLI+replay/minimize(14)=PASS ai-code-review=PASS(opus)
**Implemented directly in the main session** (not via a spawned agent — the two prior agents both stalled on a background-wait bug).

## Public API / CLI surface
- `cloudforge variation run <spec> --out <dir> --run-id X` — compose+validate+report the sweep;
  writes the run tree **directly under `--out`** (so `--out <dir>` ⇒ `<dir>/manifest.json`), `--run-id`
  stamped as the manifest/summary label. Exit 1 on abort.
- `cloudforge variation summarize <dir>` — print rollup + diversity metrics.
- `cloudforge variation replay <dir> --scenario-id X` — determinism proof (exit 1 on mismatch).
- `cloudforge variation minimize-failure <dir> --scenario-id X` — shrink a captured failure.
- Wired via `app.add_typer(variation_app, name="variation")`; all handlers `_CLI_ERRORS`-wrapped.

## The --out / --run-id reconciliation (design note)
The ticket verifier expects the manifest **directly under `--out`** (`--out _verif --run-id verif`
→ `_verif/manifest.json`), but the merged `run_suite(spec, out_dir, run_id)` writes to
`out_dir/run_id`. Rather than change `run_suite`'s contract (depended on by 1e/1g), the CLI treats
`--out` as the run directory: it calls `run_suite(spec, out.parent, out.name)` then `_relabel_run`
stamps the manifest + summary `run_id` to the `--run-id` value. The reviewer verified this is robust
(bare/trailing-slash/nested paths) and that no consumer derives a path from `run_id`.

## Bugfix included (found while wiring the CLI)
`replay._find_entry` (merged in FXL-VAR-1e) raised a bare `ValueError` on an unknown `scenario_id`.
`ValueError` is NOT in `_CLI_ERRORS`, so it would escape the new `variation replay` handler as a raw
traceback — violating the no-traceback AC (FXL-N4 / stress-contract S1/S15). Changed to
`CloudforgeError`; the 1e replay/minimize tests still pass (no regression).

## Review gate (fresh-context Opus)
- **Cycle 1 → PASS** (0 P1, 0 P2, 1 P3). Deep verification: verifier passes end-to-end; `_relabel_run`
  round-trips faithfully; `_CLI_ERRORS` covers every handler; SECURE (scenario_id gated by manifest
  lookup before any path build — `../../etc/passwd` traversal rejected cleanly; no subprocess/apply/
  credential surface); rules clean; 22 integration tests pass.
- **P3 (fixed post-review):** `summarize` help text said `<out>/<run-id>`, contradicting the
  tree-directly-under-`--out` layout → corrected. Doc-only; the cycle-2 delta had no logic surface, so
  no redundant re-review was dispatched.

## Notes
- Tests hermetic (terraform forced absent) → ~1s, no provider download. The real-terraform CLI path
  (exit 0, manifest at the verifier's exact path) was verified separately + runs in CI's External-tools job.

**Blockers**: none. Ready to merge; merging leaves only FXL-VAR-1g (diversity gate + ci/large profiles)
and FXL-VAR-1h (docs + large-run evidence) in the epic.
