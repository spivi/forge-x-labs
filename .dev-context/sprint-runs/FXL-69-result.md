# Sprint Result: FXL-69

**Status**: SUCCESS
**PR**: #94 (https://github.com/spivi/forge-x-labs/pull/94) — NOT merged
**Branch**: feat/FXL-69-quality
**Files Changed**: 3  **Tests Added**: 32
**Validation**: ruff=PASS mypy=PASS pytest=PASS (quality.py=100%, quality_dimensions.py=100%, overall app=97%+)
**Blockers**: none

## What shipped

Deterministic, rubric-based quality + realism scoring per design §9.4, implemented
in `app/cloudforge/learn/quality.py` (was a stub — `# Implemented in ticket #11`).

- `score_pattern(pattern: RiskPattern) -> tuple[RiskPattern, PatternQualityReport]` —
  scores `quality_score` + `realism_score` onto a copy of `pattern` (never mutates
  the input) and returns them alongside a `PatternQualityReport`.
- `PatternQualityReport` (new Pydantic model, `extra="forbid"`) —
  `pattern_id`, `rejection_reasons: list[str]`, `warnings: list[str]`,
  `exportable: bool`. **API note**: the ticket's acceptance criteria describe
  `score_pattern(pattern) -> RiskPattern` "+ rejection info" — `rejection_reasons` /
  `warnings` / `exportable` are not (and per scope must not become) fields on
  `RiskPattern` itself, so `score_pattern` returns `(scored_pattern, report)`,
  mirroring the `dedup() -> (survivors, DedupReport)` convention already
  established in `dedup.py`.
- `summarize_corpus(patterns: list[RiskPattern], *, duplicates: int = 0) -> CorpusSummary` —
  corpus-level aggregation: total/valid/exportable/restricted/unsafe/rejected/
  duplicates counts, `average_quality`, `top_rejection_reasons` (most common,
  top 5), and `provider_coverage` / `domain_coverage` / `weakness_family_coverage`
  dicts. `duplicates` is an optional pass-through hint (e.g. from a future
  `DedupReport`) — this module does not perform dedup itself.
- `app/cloudforge/learn/quality_dimensions.py` (new helper module, split out to
  keep `quality.py` under the 200-line cap) — five pure dimension-scoring
  functions, each a deterministic function of the pattern's own fields.
- `tests/cloudforge/learn/test_quality.py` (new) — 32 tests, built on the shared
  `build_pattern()` fixture (`tests/cloudforge/learn/conftest.py`) via
  `model_copy`, plus real end-to-end scoring of the 14-entry seed catalog
  through the actual `rule_catalog_yaml` adapter + `PatternNormalizer`.

## Dimensions + weights (design §9.4)

`quality_score` is a weighted sum of six 0..1 dimensions (weights sum to 1.0):

| Dimension | Weight | Scoring rule |
|---|---|---|
| Provenance completeness | 0.20 | fraction of 9 required provenance string fields non-blank + small bonus for non-empty `notes` |
| Fragment richness | 0.20 | 0 if no nodes; 0.2 if <2 nodes or <1 edge; 0.6–1.0 scaling with node/edge count once the ≥2 nodes / ≥1 edge floor is met (caps at 4 nodes / 2 edges) |
| Findings coverage | 0.20 | 0 if no `ExpectedFinding` references a fragment node; 0.5–1.0 scaling with count of referencing findings (caps at 2) |
| Control mapping | 0.15 | 1.0 if both `control_mappings` and `missing_controls` present; 0.6 if only one; 0.0 if neither |
| Confidence | 0.15 | `pattern.confidence` carried through verbatim (adapter-stamped) |
| Realism | 0.10 | the pattern's own `realism_score` (see below), folded in at a lower weight |

`realism_score` is scored **separately** (also stored back on the pattern) via
`quality_dimensions.realism_score`: starts at a neutral 0.7 baseline, then applies
deterministic penalties/bonuses —
a high/critical-severity pattern with an empty fragment AND no `risky_relationships`
loses 0.5 (incoherent: severe claim, zero structure); edge-less-but-noded loses 0.25;
a coherent high/critical pattern (fragment + relationships) gains 0.15;
relationships claimed with zero `affected_resource_types` lose 0.3; having both
resource types and fragment nodes gains 0.1. Clamped to `[0, 1]`.

`exportable` (convenience only, NOT the real export gate — that's ticket #71's
`export.py`) = `quality_score >= 0.70 AND no hard rejection reason`. Hard rejection
reasons: `safety_classification == unsafe_operational`, `validation_status ==
invalid`, empty `graph_fragment.nodes`, or no `expected_findings`. Softer issues
(no edges, no control mappings, low confidence, below the 0.70 bar) surface as
`warnings`, not rejections.

## Determinism

`test_scoring_is_deterministic_same_pattern_same_scores` and
`test_scoring_is_deterministic_across_many_repeats` (20x on the same pattern)
confirm identical `quality_score`/`realism_score`/`rejection_reasons`/`warnings`/
`exportable` every time — every dimension helper is a pure function of the
pattern's own fields; no randomness, no I/O, no ML/embeddings anywhere.
`test_real_seed_catalog_scores_all_14_patterns_deterministically` re-runs
`score_pattern` twice over the full real 14-seed corpus and asserts byte-identical
`quality_score` lists.

## Rich vs. sparse discrimination

- `test_rich_well_provenanced_pattern_scores_higher_than_sparse_pattern`: the shared
  `build_pattern()` fixture (2-node/1-edge fragment, 1 finding, control mappings,
  confidence 0.75) scores higher than the same pattern stripped to an empty
  fragment, no findings, no control mappings, confidence 0.1.
- `test_pattern_missing_findings_and_fragment_scores_lower_than_baseline`,
  `test_fragment_richness_increases_with_more_structure`,
  `test_findings_coverage_increases_quality_score`,
  `test_control_mapping_presence_increases_quality_score` /
  `test_control_mapping_partial_presence_scores_between_both_and_neither`,
  `test_low_adapter_confidence_lowers_quality_score` each isolate one dimension.
- `test_realism_penalizes_critical_severity_with_empty_fragment` and
  `test_realism_rewards_plausible_relationship_for_severity` cover the incoherent-
  combo requirement explicitly.
- `test_seed_with_added_finding_scores_higher_than_seed_without` demonstrates the
  discrimination on a **real seed** pattern (not just the synthetic fixture):
  the first real catalog entry, normalized, scores higher once an `ExpectedFinding`
  is attached.

## Real 14-seed corpus summary (via `rule_catalog_yaml` adapter + `PatternNormalizer`)

```
total=14  valid=0  exportable=0  restricted=0  unsafe=0  rejected=14  duplicates=0
average_quality=0.413

provider_coverage:         {"aws": 9, "azure": 2, "gcp": 3}
domain_coverage:           {"storage": 5, "iam": 5, "serverless": 1, "network": 2,
                             "encryption": 3, "logging": 1, "containers": 1,
                             "secrets": 2, "ci_cd": 1}
weakness_family_coverage:  {"public_exposure": 7, "other": 1, "iam_passrole_risk": 1,
                             "missing_encryption": 1, "missing_logging": 1,
                             "excessive_privilege": 1, "secrets_exposure": 2}

top_rejection_reasons: ["no expected_findings reference the fragment"]
```

Per-pattern quality/realism (all 14, id truncated to the catalog slug):

| id | quality | realism | severity |
|---|---|---|---|
| s3-missing-access-logging-aws-001 | 0.432 | 0.800 | medium |
| s3-public-read-no-compensating-control-aws-002 | 0.408 | 0.550 | high |
| iam-broad-s3-read-sensitive-bucket-aws-003 | 0.408 | 0.550 | high |
| iam-passrole-chain-sensitive-runtime-aws-004 | 0.408 | 0.550 | critical |
| security-group-ssh-open-to-internet-aws-005 | 0.408 | 0.550 | high |
| security-group-admin-ui-open-to-internet-aws-006 | 0.408 | 0.550 | critical |
| kms-key-policy-wildcard-principal-aws-007 | 0.408 | 0.550 | high |
| cloudtrail-logging-missing-aws-008 | 0.408 | 0.550 | high |
| storage-account-public-blob-access-azure-009 | 0.408 | 0.550 | high |
| key-vault-public-network-access-azure-010 | 0.408 | 0.550 | high |
| storage-bucket-public-iam-member-gcp-011 | 0.408 | 0.550 | high |
| service-account-overprivileged-project-role-gcp-012 | 0.408 | 0.550 | high |
| cicd-pipeline-long-lived-static-cloud-creds-aws-013 | 0.432 | 0.800 | medium |
| secret-manager-secret-overly-broad-iam-access-gcp-014 | 0.432 | 0.800 | medium |

**Why every real seed is currently "rejected" / non-exportable**: the
`PatternNormalizer` (ticket #66, out of scope here — read only) hard-codes
`risky_relationships=[]`, `missing_controls=[]`, `control_mappings=[]`, and
`expected_findings=[]` for every adapter today, and builds only a minimal
edge-less one-node-per-resource-type fragment for the rule-catalog source (no
embedded graph). Verified directly: normalizing the first seed entry produces a
1-node/0-edge fragment, empty findings/control-mappings, confidence 0.75. This is
upstream of `quality.py` — scored "as given," per the ticket's explicit
instruction not to fix normalizer over-generalization (issue #93 is the tracked,
separate normalizer concern). The `test_seed_with_added_finding_scores_higher_
than_seed_without` test confirms the scoring rubric itself correctly rewards a
seed the moment it's enriched with an `ExpectedFinding` — the scoring logic is
verified correct against real seed data; the flat 0.41 average reflects the
current normalizer's sparse output, not a scoring defect.

## Acceptance criteria — all met

- [x] `score_pattern(pattern) -> RiskPattern` with `quality_score` + `realism_score`
      set, plus rejection info — delivered as `(RiskPattern, PatternQualityReport)`
      (see API note above; `RiskPattern` is unmodified, so the report can't live on
      it). `summarize_corpus(patterns) -> CorpusSummary` (coverage + averages).
- [x] Deterministic: same input → identical scores
      (`test_scoring_is_deterministic_same_pattern_same_scores`,
      `test_scoring_is_deterministic_across_many_repeats`,
      `test_real_seed_catalog_scores_all_14_patterns_deterministically`).
- [x] Rubric-based, NO ML/embeddings/learning — six pure weighted dimensions, no
      randomness, no training, no vector similarity anywhere in either module.
- [x] Rich pattern scores higher than sparse
      (`test_rich_well_provenanced_pattern_scores_higher_than_sparse_pattern`,
      `test_seed_with_added_finding_scores_higher_than_seed_without` on a real
      seed); pattern missing findings/fragment scores lower
      (`test_pattern_missing_findings_and_fragment_scores_lower_than_baseline`);
      realism penalizes critical severity + empty fragment
      (`test_realism_penalizes_critical_severity_with_empty_fragment`).
- [x] Corpus summary reports provider/domain/weakness_family coverage over the
      real 14-seed catalog (`test_summarize_corpus_reports_provider_domain_
      family_coverage` — aws≥8, azure≥2, gcp≥3 asserted and verified above).
- [x] `ruff` (0.9.4) + `mypy --strict` clean; coverage ≥80% (`quality.py` and
      `quality_dimensions.py` both 100% from the dedicated test file alone;
      app-wide 97%+). `quality.py` = 199 lines, `quality_dimensions.py` = 143
      lines (both ≤200); every function ≤30 lines and ≤3 params (Pydantic models
      used for wider data instead of longer signatures).

## Validation detail

- `ruff check app/cloudforge/learn/quality.py app/cloudforge/learn/quality_dimensions.py tests/cloudforge/learn/test_quality.py --fix` — clean (one line-length fix auto-applied)
- `ruff format` (same files) — reformatted once, stable after
- `ruff check app/ tests/ --fix` / `ruff format app/ tests/` (whole repo) — clean, no other files touched
- `mypy --strict app/` — 60 source files, no issues
- `PYTHONPATH=. .venv/bin/pytest tests/cloudforge/learn/test_quality.py -q --no-cov` — 32 passed
- `PYTHONPATH=. .venv/bin/pytest tests/cloudforge/learn/test_quality.py --cov-report=term-missing` — `quality.py` 100%, `quality_dimensions.py` 100%
- `PYTHONPATH=. .venv/bin/pytest tests/cloudforge/ -q --no-cov` — 332 passed, 9 deselected (no regressions)
- `PYTHONPATH=. .venv/bin/pytest tests/cloudforge/ -q` (coverage gate) — 330 passed at time of check (pre-final-2-tests run), 97.48% total, gate (80%) cleared; re-ran bare suite after adding 2 more tests → 332 passed
- CI on PR #94 — polled 3x via `gh pr checks 94 --watch`; 0 failures across all polls (14→9 pending drained to 8, then 4 remaining, all green). No red checks observed. `gh pr view 94` confirms `state=OPEN`, `mergeable=MERGEABLE`.

## Scope discipline

Touched only `app/cloudforge/learn/quality.py` (implemented, was a stub),
the new `app/cloudforge/learn/quality_dimensions.py` helper (to respect the
200-line module cap), and the new `tests/cloudforge/learn/test_quality.py`.
Did not modify `pattern_models.py`, `normalizer.py`, `validate.py`, or `dedup.py`
(read only, per instructions). Did not implement `corpus.py` / `export.py` /
CLI wiring — all remain their pre-existing stubs. No `RiskPattern` fields added
or changed. Did not attempt to fix the normalizer's known weakness_family
over-generalization (issue #93) or its hard-coded empty
`risky_relationships`/`missing_controls`/`control_mappings`/`expected_findings`
— out of scope, scored patterns exactly as the normalizer emits them today. PR
was not merged — left open for review per instructions.
