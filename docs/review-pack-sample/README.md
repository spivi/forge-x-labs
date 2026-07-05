# Sample Review Pack — 10 scenarios

Ten review sheets assembled from **real cloudforge output**, for use with the [quality rubric](../review-rubric.md) and the [1-page format](../review-pack-template.md). Each sheet is one scenario: a ground-truth-**hidden** reviewer view (score blind) followed by a **reveal**.

## How this pack was generated

From the repo root, against the two shipped families and the deterministic mutation engine:

```bash
# base families
python -m app.cli generate examples/ci_cd_iam_chain.yaml     --out out/ci
python -m app.cli generate examples/public_data_exposure.yaml --out out/pub
# seeded, ground-truth-preserving mutations (seeds 1..4 per family)
python -m app.cli generate examples/ci_cd_iam_chain.yaml     --out out/ci-s1  --mutate-seed 1
#   ... seeds 2,3,4 for ci_cd_iam_chain, seeds 1..4 for public_data_exposure
python -m app.cli report out/ci   # renders report.md per scenario
```

Each sheet's fields are copied from that scenario's `report.md`, `graph.json`, `ground_truth_paths.json`, and `expected_findings.json` — nothing is invented. The raw `out/` artifact trees are gitignored; only these assembled 1-page sheets are committed.

## Contents

| # | Sheet | Family | Variant | Nodes | Edges | Findings | Critical sev |
|:-:|-------|--------|---------|:-:|:-:|:-:|:-:|
| 01 | [`01-ci_cd_iam_chain--base.md`](01-ci_cd_iam_chain--base.md) | `ci_cd_iam_chain` | base | 14 | 11 | 5 | critical |
| 02 | [`02-ci_cd_iam_chain--seed1.md`](02-ci_cd_iam_chain--seed1.md) | `ci_cd_iam_chain` | seed 1 | 15 | 12 | 5 | critical |
| 03 | [`03-ci_cd_iam_chain--seed2.md`](03-ci_cd_iam_chain--seed2.md) | `ci_cd_iam_chain` | seed 2 | 15 | 12 | 5 | critical |
| 04 | [`04-ci_cd_iam_chain--seed3.md`](04-ci_cd_iam_chain--seed3.md) | `ci_cd_iam_chain` | seed 3 | 15 | 12 | 5 | critical |
| 05 | [`05-ci_cd_iam_chain--seed4.md`](05-ci_cd_iam_chain--seed4.md) | `ci_cd_iam_chain` | seed 4 | 15 | 12 | 5 | critical |
| 06 | [`06-public_data_exposure--base.md`](06-public_data_exposure--base.md) | `public_data_exposure` | base | 7 | 5 | 3 | critical |
| 07 | [`07-public_data_exposure--seed1.md`](07-public_data_exposure--seed1.md) | `public_data_exposure` | seed 1 | 8 | 6 | 3 | critical |
| 08 | [`08-public_data_exposure--seed2.md`](08-public_data_exposure--seed2.md) | `public_data_exposure` | seed 2 | 8 | 6 | 3 | critical |
| 09 | [`09-public_data_exposure--seed3.md`](09-public_data_exposure--seed3.md) | `public_data_exposure` | seed 3 | 8 | 6 | 3 | critical |
| 10 | [`10-public_data_exposure--seed4.md`](10-public_data_exposure--seed4.md) | `public_data_exposure` | seed 4 | 8 | 6 | 3 | critical |

## What the mutations exercise

The 8 seeded variants rename resource **display labels** and add one benign, unconnected decoy node — while leaving the ground-truth critical-path node IDs and edges **byte-identical** to their base (verified per sheet in the reveal). This lets a reviewer probe two things the base scenarios can't: (1) does a cosmetic rename change the realism read, and (2) does the reviewer correctly ignore the benign decoy. It is also the human-facing evidence for point #12 of the 12-point validated definition ([FXL-D003](../../.dev-context/DECISIONS.md)): *mutation, if used, preserves ground truth.*
