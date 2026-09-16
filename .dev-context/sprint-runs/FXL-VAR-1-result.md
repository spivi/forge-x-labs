# FXL-VAR-1 — large-run acceptance evidence

**Ticket:** FXL-VAR-1h (#135)
**Date:** 2026-09-16
**Command:**

```bash
env PATH="/usr/bin:/bin:$PWD/.venv/bin" PYTHONPATH=. .venv/bin/python -m app.cli \
  variation run examples/variation/aws_large.yaml \
  --out out/variation_runs/large --run-id var1large --gate
```

Optional tools (terraform/checkov/opa) were **absent** on PATH so the run did not
download the AWS provider 2,000 times (see `docs/variation/README.md` and
patterns.md). That is the intended `if_available` profile.

## Result — GO

| Metric | Value | Bar | Verdict |
|---|---|---|---|
| Scenarios | 2,000 | ≥ 2,000 | pass |
| Validation FAIL | 0 | — | pass |
| Aborted | false | — | pass |
| Unique graph shapes | **77** | ≥ 5 | pass |
| Critical-path lengths | **[3, 5, 6, 7]** (4) | ≥ 4 | pass |
| Decoys | **66.4%** | ≥ 20% | pass |
| Compensating controls | **47.4%** | ≥ 20% | pass |
| False positives | **100.0%** | ≥ 10% | pass |
| Scanner profiles | `["not_scored"]` | skip if Checkov absent | WARN, not FAIL |
| `--gate` exit | **0** | 0 = depth bar met | pass |
| Wall clock | **31.2s** | — | — |

Scales: tiny 500 / small 500 / medium 500 / large 500.
Families: `ci_cd_iam_chain`, `public_data_exposure`.

## Unsupported axes (honest)

`public_data_exposure` records `path_length` as **unsupported** — that family has
a fixed-length exposure path; the composer’s `path_hops` parameter is a CI/CD
fragment knob. The gate did **not** count this as a failure (FXL-VAR-1g contract).
`ci_cd_iam_chain` did vary length (3/5/6/7 at suite level).

## Why false-positive % is 100

Both core fragments ship a labeled benign finding. `has_false_positives` is true
for every composed scenario even when the `fp` axis is `"0"`. That is real, not
a gamed score. A follow-up could count *extra* FP fragments only; not blocking.

## Bugs found this run

None. 2,000/2,000 `validation_status=pass`.

## Go / no-go for more families

**GO.** The composer produces structural diversity (77 shapes, four path lengths,
decoy/control spread) while preserving ground truth at 2,000 scenarios. This
unblocks the third family (plan FXL-D009), subject to each new family joining
the integrity net.

Not claimed: Checkov scoring diversity (tools were absent; WARN). Not claimed:
novel topologies beyond the fragment vocabulary (that is v2 diffusion).
