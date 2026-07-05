# FXL-E2 — Cloud Risk Pattern Learning Corpus (issues mirror)

In-repo mirror of the epic + its 18 child issues on GitHub, per the convention in
[`README.md`](README.md) (project management lives on GitHub Issues + Project board #6;
this directory mirrors it locally). All issues below were **created successfully** and added
to the board — this file is a record, not a fallback.

- **Milestone:** [`E2 - Cloud Risk Pattern Learning Corpus`](https://github.com/spivi/forge-x-labs/milestone/9) (milestone #9)
- **Epic issue:** [#76 — FXL-E2: Cloud Risk Pattern Learning Corpus](https://github.com/spivi/forge-x-labs/issues/76)
- **Design doc:** [`docs/plans/2026-07-05-FXL-E2-learning-corpus-design.md`](../plans/2026-07-05-FXL-E2-learning-corpus-design.md)
- **Project board:** [project #6](https://github.com/users/spivi/projects/6) (all 19 items added)

## Child issues (build order)

| Order | # | Title | Effort |
|---|---|-------|--------|
| 1 | [#60](https://github.com/spivi/forge-x-labs/issues/60) | Define RiskPattern and provenance models | M |
| 2 | [#58](https://github.com/spivi/forge-x-labs/issues/58) | Add source registry model and file | S |
| 3 | [#61](https://github.com/spivi/forge-x-labs/issues/61) | Add learning package structure | S |
| 4 | [#59](https://github.com/spivi/forge-x-labs/issues/59) | Add raw source fetcher and cache | M |
| 5 | [#62](https://github.com/spivi/forge-x-labs/issues/62) | Implement rule catalog YAML adapter | M |
| 6 | [#63](https://github.com/spivi/forge-x-labs/issues/63) | Implement cloudforge scenario adapter | M |
| 7 | [#64](https://github.com/spivi/forge-x-labs/issues/64) | Implement Checkov policy index adapter (metadata-only) | M |
| 8 | [#65](https://github.com/spivi/forge-x-labs/issues/65) | Implement PatternNormalizer | M |
| 9 | [#66](https://github.com/spivi/forge-x-labs/issues/66) | Implement graph fragment validation | M |
| 10 | [#67](https://github.com/spivi/forge-x-labs/issues/67) | Implement deterministic dedup | M |
| 11 | [#68](https://github.com/spivi/forge-x-labs/issues/68) | Implement quality scoring | M |
| 12 | [#69](https://github.com/spivi/forge-x-labs/issues/69) | Implement corpus validation | M |
| 13 | [#70](https://github.com/spivi/forge-x-labs/issues/70) | Implement training export | M |
| 14 | [#71](https://github.com/spivi/forge-x-labs/issues/71) | Add seed rule catalog (>=12 patterns) | M |
| 15 | [#72](https://github.com/spivi/forge-x-labs/issues/72) | Add learn CLI commands | M |
| 16 | [#73](https://github.com/spivi/forge-x-labs/issues/73) | Add internet-marked integration tests | S |
| 17 | [#74](https://github.com/spivi/forge-x-labs/issues/74) | Add docs for source registry and provenance | S |
| 18 | [#75](https://github.com/spivi/forge-x-labs/issues/75) | Add docs for future diffusion training | S |

> Issue-number order (#58…#75) reflects creation order; the **build order** column is the
> dependency-correct sequence (models+registry+skeleton → adapters → normalizer+fragment
> validation → dedup+quality → corpus-validate+export → seeds → CLI → integration tests → docs).

## Reproduce (exact `gh` commands)

```bash
# Milestone
gh api repos/spivi/forge-x-labs/milestones \
  -f title="E2 - Cloud Risk Pattern Learning Corpus" -f state="open" \
  -f description="Local-first learning-corpus pipeline ... (see design doc)"

# Each child (body files are the per-ticket specs; labels: enhancement, or documentation for #74/#75)
gh issue create --repo spivi/forge-x-labs \
  --title "FXL-E2: <child title>" --body-file <spec.md> \
  --milestone "E2 - Cloud Risk Pattern Learning Corpus" --label enhancement

# Epic
gh issue create --repo spivi/forge-x-labs \
  --title "FXL-E2: Cloud Risk Pattern Learning Corpus" --body-file <epic.md> \
  --milestone "E2 - Cloud Risk Pattern Learning Corpus" --label enhancement

# Board (repeat per issue #)
gh project item-add 6 --owner spivi --url https://github.com/spivi/forge-x-labs/issues/<N>
```

## Human calls the coordinator must make

- **CSA CCM & CIS Benchmarks reuse rights.** Both default to `restricted` / not-training-eligible
  in `data/source_registry.yaml` until a human confirms. Control-ID **mappings** are safe;
  copying their control **text** is not. Record any upgrade as an `FXL-D` decision.
