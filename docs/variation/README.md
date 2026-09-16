# Variation harness

`cloudforge variation` composes many seeded scenarios, validates them, and
measures whether the generator produces **structural** diversity (graph shape,
path length, decoys, false positives, compensating controls) rather than
renamed copies of the same graph.

Cosmetic mutation (`--mutate-seed`) is a different engine. Names, tags, and the
one benign extra subnet **must not** count toward a shape signature. The
diversity gate is the acceptance test for generator *depth*.

Safety is structural: `no_apply` and `no_credentials` cannot be set false.
Nothing in this harness runs `terraform apply` or reads cloud credentials.

## Profiles

| Spec | Size | When |
|---|---|---|
| `examples/variation/aws_smoke.yaml` | 2 families × tiny × 5 seeds = **10** | quick local |
| `examples/variation/aws_ci.yaml` | 2 families × tiny+small × 25 seeds = **100** | PR/CI |
| `examples/variation/aws_large.yaml` | 2 families × tiny/small/medium/large × 250 seeds = **2,000** | manual/nightly evidence |

```bash
PYTHONPATH=. .venv/bin/python -m app.cli variation run \
  examples/variation/aws_smoke.yaml --out out/variation_runs/smoke --run-id smoke

PYTHONPATH=. .venv/bin/python -m app.cli variation run \
  examples/variation/aws_ci.yaml --out out/variation_runs/ci --run-id ci --gate

# ≥2,000 scenarios. Hide terraform/checkov/opa unless you intend to download
# the AWS provider once per scenario (disk + time). See patterns.md.
PYTHONPATH=. .venv/bin/python -m app.cli variation run \
  examples/variation/aws_large.yaml --out out/variation_runs/large --run-id var1large --gate
```

`--gate` exits 1 and prints `cosmetic variation only` when the depth bar is
missed. A 0-FAIL suite that is still only cosmetic is **not** success.

Without `--gate`, `run` still writes the tree and exits 0 unless the suite
aborts (too many validation FAILs).

## Run tree

`--out DIR` **is** the run directory (`DIR/manifest.json`). `--run-id` is a
label stamped into the manifest, not necessarily the directory name.

```
<out>/
  variation_spec.yaml
  manifest.json              # one entry per scenario; artifact_dir is relative
  summary.json
  diversity_report.json
  scenarios/<id>/            # full generate/validate/report tree
  failures/raw/
  failures/minimized/
```

`cloudforge variation summarize <out>` prints the rollup.
`cloudforge variation replay <out> --scenario-id <id>` proves byte-identical
regeneration. `minimize-failure` shrinks a captured FAIL and never deletes the
original.

## Reading `diversity_report.json`

| Field | Meaning |
|---|---|
| `unique_graph_shapes` | Distinct `shape_signature` values. Signature hashes node/edge **type counts** (bucketed), path length, finding families, and decoy/FP/control *presence*. Display `name`/`tags` are never read. The mutation engine's extra subnet is canonicalized out. |
| `critical_path_lengths` | Distinct ground-truth path lengths in the suite. |
| `pct_with_decoys` / `pct_with_false_positives` / `pct_with_compensating_controls` | Percents 0–100. |
| `scanner_score_profiles` | `["not_scored"]` when Checkov did not run (WARN, not a fake pass). |
| `unsupported_axes` | `{family: ["path_length", …]}` when an axis was requested but that family cannot vary it. Counted as unsupported, **not** as a failed threshold. |

### Gate thresholds (design §5)

These **are** the depth bar (`app/cloudforge/variation/gate.py`):

- ≥ 5 distinct graph-shape signatures
- ≥ 4 distinct critical-path lengths, unless `path_length` is unsupported for every family in the run
- ≥ 3 scanner-score profiles **if** Checkov actually scored; skipped (WARN) when profiles are only `not_scored`
- ≥ 20% decoys, ≥ 20% compensating controls, ≥ 10% false positives

`evaluate_gate` reads the live report file the suite runner writes (suite-level
metrics, percents on 0–100). It does not use a separate per-family schema.

## Integration tests

Force optional tools absent so CI does not download the AWS provider:

```python
monkeypatch.setattr(tool_probe, "detect_tool", lambda name: False)
```
