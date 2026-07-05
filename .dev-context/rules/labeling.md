# Ticket Labeling (ML-ready)

Every ticket is labeled with **typed dimensions** so outcomes can be learned
mathematically over time. These are first-class columns in
`.dev-context/kpis/estimates.csv` — not buried in a free-form string.

## Typed dimensions

| dimension | column | allowed values | source of truth |
|---|---|---|---|
| type | `type` | feature, fix, tweak, refactor, docs, chore, spike | set by `/prd` |
| effort | `effort` | `S` `M` `L` `XL` | set by `/prd` |
| milestone | `milestone` | open vocabulary (e.g. M0, M1, beta) | set by `/prd` |
| risk | `risk` | `low` `medium` `high` | set by `/prd` |
| area | `area` | open vocabulary (e.g. api, ui, infra, data) | set by `/prd` |
| priority | `priority` | open vocabulary (e.g. P1, P2) | set by `/prd` |

The single source of truth for the dimension set is
`.dev-context/planning/taxonomy.yml`. **To add a dimension** (e.g. `surface`):
1. Add it under `dimensions:` in `taxonomy.yml` (column + allowed + `label_prefix`).
2. Add the column to `scripts/trackers/store.py::COLUMNS` (after `labels`).
3. Add a `FIELD_SPECS` row in `scripts/dataset.py` so it surfaces as an ML feature.
No estimator/debrief code changes are required — they read columns generically.

## How to stamp labels

```bash
python scripts/tracker.py plan ABC-42 --type feature --effort L \
  --milestone M1 --risk high --area api --priority P2
```

`labels` (the legacy semicolon string, e.g. `effort:L;area:api`) is still accepted
and is used as a **fallback** when a typed column is blank. Migrate old CSVs once:

```bash
python scripts/tracker.py migrate    # widens 13-col -> 17-col, back-fills from labels
```

## The learning loop

- `/prd` → `scripts/estimator.py` stamps `estimate_minutes` + `recommended_model`
  (cheapest-sufficient: the effort floor, up-tiered only when the learned policy
  shows a class is underpowered).
- `/debrief` → `scripts/debrief.py` joins estimates × `cost-ledger.csv` actuals ×
  `reviews.csv` outcomes, learning per-dimension `calibration.json` (estimate
  factors) and `model-policy.json` (routing) on `type:` / `label:effort:` /
  `label:risk:` / `label:area:` keys, then emits the ML-ready
  `kpis/dataset.csv` (+ `FEATURES.md` data dictionary).
- One tidy row per ticket = typed-label **features** + measured **outcomes**
  (duration, tokens, cost, review findings, suitability verdict). That table is
  the ML on-ramp.

**Rule:** never invent ad-hoc label keys. Use the taxonomy dimensions so the
learning loop and dataset stay consistent and comparable across tickets.
