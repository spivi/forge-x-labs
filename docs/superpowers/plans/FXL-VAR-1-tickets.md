# FXL-VAR-1 — Ticket Breakdown (8 deliverables)

Source of truth for the GitHub issue bodies. Each ticket = one independently-reviewable
deliverable from `2026-07-06-FXL-VAR-1-variation-validation.md`, with **acceptance criteria**
and a **verifier** (the exact command a reviewer/agent runs to prove it done).

Merge order (serial spine in Phase 1; harness parallelizes after 1c):
`1a → 1b → 1c → {1d, 1e, 1f} → 1g → 1h`

Labels: all `type:feature`, `milestone:M2`, `area:generation` (1a–1c) / `area:harness` (1d–1h).
Risk: `high` for 1c (composer/integrity — the ground-truth-preserving core), else `medium`.

---

## FXL-VAR-1a — Fragment registry + core fragments (plan T1–T3)

**Scope:** `generate/fragments/base.py` (FragmentBundle + registry), `core_ci_cd.py`
(parameterized path length), `core_public_data.py`. The two existing hardcoded families become
ns-prefixed `core.*` fragments; default params reproduce today's baseline.

**Acceptance criteria:**
- `core.ci_cd_iam_chain` and `core.public_data_exposure` are registered and retrievable via
  `get_fragment`; `all_kinds()` lists both.
- Each fragment's `FragmentBundle` is internally consistent: every finding `resource_id` and every
  ground-truth edge key references only that fragment's own (ns-prefixed) ids.
- `path_hops` param lengthens the ci_cd critical path (more hops → more path nodes).

**Verifier:**
```bash
PYTHONPATH=. .venv/bin/pytest tests/unit/generate/fragments/ -q --no-cov && \
ruff check app/cloudforge/generate/fragments/ && mypy --strict app/cloudforge/generate/fragments/
```

---

## FXL-VAR-1b — Non-core fragments + scale profiles (plan T4–T5)

**Scope:** `fragments/decoy.py`, `false_positive.py`, `compensating_control.py`,
`benign_noise.py`; `generate/scale_profiles.py`; optional `scale_profile`/`variation_axes` on
`ScenarioSpec`.

**Acceptance criteria:**
- `decoy.*` owns nodes but **no** ground-truth path; `benign_noise.*` owns **no** findings and no
  paths; `false_positive.*` owns a `ground_truth == "benign"` finding; `compensating_control.*`
  owns **no** finding.
- No non-core fragment emits a destructive/forbidden IAM action (names/tags/actions from fixed
  benign vocab only).
- 5 scale profiles (`tiny..xlarge`) with monotonic node bands; `xlarge.emit_terraform is False`.
- Existing `examples/*.yaml` still load (new spec fields are optional/defaulted).

**Verifier:**
```bash
PYTHONPATH=. .venv/bin/pytest tests/unit/generate/fragments/test_noncore_fragments.py \
  tests/unit/generate/test_scale_profiles.py -q --no-cov && \
PYTHONPATH=. .venv/bin/pytest tests/ -k "scenario_spec or examples" -q --no-cov
```

---

## FXL-VAR-1c — GraphComposer engine + integrity net + CLI (plan T6–T8) — RISK:high

**Scope:** `generate/composer.py` (`GraphComposer` + `ComposerGenerator`), the integrity
regression test, and `--engine composer --seed N` on `cloudforge generate`.

**Acceptance criteria:**
- Same `(spec, seed)` → byte-identical `graph.json`/`expected_findings.json`/`ground_truth_paths.json`.
- All composed node ids globally unique (collision raises, never silently dedups).
- Scale profile fills the node band (e.g. `medium` → 75–150 nodes).
- **Integrity net (the load-bearing gate):** across families × seeds `{0,1,2,17,99}`, every composed
  scenario passes `run_validations` with **zero FAIL** outcomes.
- `--engine template` (default) behavior unchanged; `--engine composer --seed N` writes a valid tree.

**Verifier:**
```bash
PYTHONPATH=. .venv/bin/pytest tests/unit/generate/test_composer.py \
  tests/integration/test_composer_integrity.py tests/integration/test_cli_composer.py \
  -q --no-cov && mypy --strict app/cloudforge/generate/
```

---

## FXL-VAR-1d — VariationSpec/Manifest + diversity metrics (plan T9–T10)

**Scope:** `variation/models.py`, `variation/diversity.py`, `examples/variation/aws_smoke.yaml`.

**Acceptance criteria:**
- `VariationSpec` loads `aws_smoke.yaml`; `VariationConstraints().no_apply is True` by default.
- `shape_signature` **excludes names/tags**: a cosmetic `MutationGenerator` variant of a bundle has
  the **same** signature as its base; a different scale profile yields a **different** signature.
- `diversity_report` counts unique signatures + the §5 distributions.

**Verifier:**
```bash
PYTHONPATH=. .venv/bin/pytest tests/unit/variation/test_models.py \
  tests/unit/variation/test_diversity.py -q --no-cov && mypy --strict app/cloudforge/variation/
```

---

## FXL-VAR-1e — Suite runner + replay/minimize (plan T11–T12)

**Scope:** `variation/suite_runner.py`, `variation/replay.py`, `variation/minimize.py`.

**Acceptance criteria:**
- `run_suite(spec, out_dir, run_id)` on smoke → 10 scenarios (2 families × 1 scale × 5 seeds), writes
  `manifest.json` + `diversity_report.json` + per-scenario `graph.json`; `run_id` is a parameter
  (never generated inside).
- Zero `FAIL` validation statuses on the smoke suite.
- `replay(run_dir, scenario_id)` returns `True` (byte-identical regeneration).
- Failure capture preserves raw artifacts + logs + exception; minimize never deletes originals.

**Verifier:**
```bash
PYTHONPATH=. .venv/bin/pytest tests/integration/test_suite_runner.py \
  tests/integration/test_replay_minimize.py -q --no-cov
```

---

## FXL-VAR-1f — Variation CLI (plan T13)

**Scope:** `variation/cli.py` (`run`/`summarize`/`replay`/`minimize-failure`), wired into `cli.py`.

**Acceptance criteria:**
- `cloudforge variation run <smoke> --out <dir> --run-id X` exits 0 and writes `manifest.json`.
- `cloudforge variation summarize <dir>` exits 0.
- All handlers wrapped in the `_CLI_ERRORS` clean-error pattern (no raw traceback on bad input).

**Verifier:**
```bash
PYTHONPATH=. .venv/bin/pytest tests/integration/test_variation_cli.py -q --no-cov && \
PYTHONPATH=. .venv/bin/python -m app.cli variation run examples/variation/aws_smoke.yaml \
  --out out/variation_runs/_verif --run-id verif && test -f out/variation_runs/_verif/manifest.json
```

---

## FXL-VAR-1g — Diversity gate + ci/large profiles (plan T14)

**Scope:** `variation/gate.py`, `--gate` flag on `variation run`, `examples/variation/aws_ci.yaml`
+ `aws_large.yaml`.

**Acceptance criteria:**
- `evaluate_gate` passes a rich report and **fails loudly** on a shallow one (< 5 shapes / 0% decoys),
  naming the failing dimension.
- Missing checkov → scanner-profile check is WARN (skipped), not FAIL; unsupported path-length axis is
  reported as `unsupported`, not counted.
- `variation run --gate` exits non-zero when the gate fails and prints "cosmetic variation only".

**Verifier:**
```bash
PYTHONPATH=. .venv/bin/pytest tests/unit/variation/test_gate.py \
  tests/integration/test_gate_cli.py -q --no-cov
```

---

## FXL-VAR-1h — Docs + large-run acceptance evidence (plan T15–T16)

**Scope:** `docs/variation/README.md`, STATUS/cc10x updates,
`.dev-context/sprint-runs/FXL-VAR-1-result.md`.

**Acceptance criteria:**
- Docs explain smoke/ci/large profiles, the run tree, how to read the diversity report + gate, and
  the safety boundaries; the documented smoke command runs clean.
- The large profile is run (≥ 2,000 scenarios) and its **honest** result recorded: profiles added,
  scenarios generated, pass/fail counts, diversity metrics, unsupported axes, bugs found/fixed, and
  the go/no-go on "ready for more families vs still needs generator depth." If the gate FAILS, it is
  reported as such with follow-up tickets — no faked success (spec §11).

**Verifier:**
```bash
PYTHONPATH=. .venv/bin/python -m app.cli variation run examples/variation/aws_large.yaml \
  --out out/variation_runs/large --run-id var1large --gate; echo "gate exit: $?" && \
test -f .dev-context/sprint-runs/FXL-VAR-1-result.md
```
