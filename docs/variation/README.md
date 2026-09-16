# Variation harness

`cloudforge variation` composes many seeded scenarios, validates them, and
measures whether the generator produces **structural** diversity (graph shape,
path length, decoys, false positives, compensating controls) rather than
renamed copies of the same graph.

Cosmetic mutation (`--mutate-seed`) is a different engine. Names, tags, and the
one benign extra subnet must not count toward a shape signature. The
diversity gate is the acceptance test for generator depth.

Nothing in this harness runs `terraform apply` or reads cloud credentials.

## Profiles

| Spec | Size | When |
|---|---|---|
| `examples/variation/aws_smoke.yaml` | 2 families x tiny x 5 seeds = **10** | quick local |
| `examples/variation/aws_ci.yaml` | 2 families x tiny+small x 25 seeds = **100** | PR/CI |
| `examples/variation/aws_large.yaml` | 2 families x tiny/small/medium/large x 250 seeds = **2,000** | manual/nightly |

```bash
PYTHONPATH=. .venv/bin/python -m app.cli variation run \
  examples/variation/aws_smoke.yaml --out out/variation_runs/smoke --run-id smoke

PYTHONPATH=. .venv/bin/python -m app.cli variation run \
  examples/variation/aws_ci.yaml --out out/variation_runs/ci --run-id ci --gate

# Hide terraform/checkov/opa unless you intend to download the AWS provider
# once per scenario.
PYTHONPATH=. .venv/bin/python -m app.cli variation run \
  examples/variation/aws_large.yaml --out out/variation_runs/large --run-id var1large --gate
```

`--gate` exits 1 and prints `cosmetic variation only` when the depth bar is
missed. A 0-FAIL suite that is still only cosmetic is not success.

Without `--gate`, `run` still writes the tree and exits 0 unless the suite
aborts (too many validation FAILs).

## Run tree

`--out DIR` is the run directory (`DIR/manifest.json`). `--run-id` is a label
stamped into the manifest.

```
<out>/
  variation_spec.yaml
  manifest.json
  summary.json
  diversity_report.json
  scenarios/<id>/
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
| `unique_graph_shapes` | Distinct `shape_signature` values. Hashes node/edge type counts, path length, finding families, and decoy/FP/control presence. Display `name`/`tags` are never read. |
| `critical_path_lengths` | Distinct ground-truth path lengths. |
| `pct_with_decoys` / `pct_with_false_positives` / `pct_with_compensating_controls` | Percents 0-100. |
| `scanner_score_profiles` | `["not_scored"]` when Checkov did not run. |
| `unsupported_axes` | Axes requested but that family cannot vary. Not a failed threshold. |

### Gate thresholds

- At least 5 distinct graph-shape signatures
- At least 4 distinct critical-path lengths, unless `path_length` is unsupported
  for every family in the run
- At least 3 scanner-score profiles if Checkov actually scored; skipped when
  profiles are only `not_scored`
- At least 20% decoys, 20% compensating controls, 10% false positives

## Integration tests

Force optional tools absent so CI does not download the AWS provider:

```python
monkeypatch.setattr(tool_probe, "detect_tool", lambda name: False)
```
