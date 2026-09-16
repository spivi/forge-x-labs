# FXL-96 Result — Normalizer preserves seed-declared fields (P1)

**Ticket:** FXL-96 (P1) — Normalizer rule-catalog path DROPS seed-declared fields.
**Branch:** `fix/FXL-96-normalizer-preserve-seed-fields`
**PR:** #97 (open, NOT merged) — https://github.com/spivi/forge-x-labs/pull/97
**Status:** Complete. Closes #96 (supersedes #93).

## The bug
The `PatternNormalizer` rule-catalog path read only the flat top-level
`RawPatternRecord` fields and IGNORED the rich `raw_payload` content the
`rule_catalog_yaml` adapter correctly preserves. Result: normalized RiskPatterns had
empty `missing_controls` / `compensating_controls` / `negative_controls` /
`risky_relationships`, and an over-generalized `weakness_family` (`public_exposure`
instead of the seed's declared family). The two AWS S3 seeds collapsed to identical
dedup keys (empty controls + same family) and one was dropped as a false duplicate.

## The fix (HONEST scope — after AI-review rework)
1. **Preserve declared list fields** — read `missing_controls` /
   `compensating_controls` / `negative_controls` / `risky_relationships` from
   `raw_payload` (tolerating a bare-string scalar), sorted + deduplicated for
   determinism, mapped onto the RiskPattern instead of dropped.
2. **Preserve the seed's declared `weakness_family`** — `resolve_weakness_family`
   honors a valid declared `weakness_family` over keyword inference; falls back to
   inference only when absent/invalid. This resolves the #93 dedup collision.
3. **NO fabricated graphs/findings.** An earlier revision synthesized
   graph_fragments + expected_findings from the flat seed fields to lift quality
   scores; the AI review gate correctly flagged that this encodes FALSE cloud
   semantics (e.g. `IAMPolicy → can_read → IAMRole` with the real bucket
   disconnected; a fabricated DataSet forced into an IAM-PassRole scenario;
   per-family templated edges the seed never declared). A seed declares a risk
   *pattern*, not a graph — so the fabrication was reverted. The fragment is now
   either a real graph embedded in `raw_payload` (the `cloudforge_scenario` path,
   reused verbatim) or an honest minimal fragment (one generic node per declared
   resource type, no invented edges). `expected_findings` stays empty. Real
   per-seed fragments/findings are a separate ticket (#98).

## Before / After (real 14-seed catalog: adapter → normalize → validate_fragment → score → dedup → summarize_corpus)

| Metric | BEFORE | AFTER |
|---|---|---|
| **Exportable (quality ≥ 0.70)** | **0/14** | **0/14** (honest — see note) |
| Valid | 13/14 (1 lost to dedup collapse) | **14/14** |
| Dedup collisions | 1 (both S3 seeds → 1 key) | **0** (both survive) |
| Average quality | 0.4133 | **0.5171** |
| Declared controls preserved | ✗ (all empty) | ✓ |
| Declared weakness_family preserved | ✗ (→ public_exposure) | ✓ |

**Note on exportable = 0/14:** this is CORRECT and honest. The rule-catalog seeds
carry no real graph_fragment yet, so — without fabricating one — they score below the
0.70 export bar (fragment-richness + findings-coverage dimensions legitimately score
low). The value delivered by THIS ticket is the corpus no longer (a) drops the
declared structured fields and (b) collapses distinct S3 risks into one. Getting these
seeds exportable requires hand-authored per-seed fragments, tracked as **#98**. An
inflated "12/14 / 14/14 exportable" number was achievable only by inventing graph
semantics — explicitly rejected in review.

## Verification of acceptance criteria
- Seed 0 `missing_controls == ['server_access_logging']` — **preserved** ✓
- Seed 0 `compensating_controls == ['cloudtrail_data_events_s3']` — **preserved** ✓
- Seed 0 `weakness_family == 's3_logging_missing'` (not `public_exposure`) — **preserved** ✓
- Two S3 seeds now have distinct families (`s3_logging_missing` / `s3_public_exposure`)
  → distinct dedup keys → **both survive** ✓
- Deterministic (sorted list fields, no randomness); safety scan intact;
  `validation_status` stays `unvalidated` ✓

## Files
- `app/cloudforge/learn/normalizer.py` — preserve declared fields + declared
  weakness_family; reuse embedded graph else minimal fragment; empty findings (187 lines).
- `app/cloudforge/learn/_fragment.py` — NEW: honest graph-fragment builder (embedded
  reuse OR minimal, no fabrication) (65 lines).
- `app/cloudforge/learn/_taxonomy.py` — `resolve_weakness_family` honors declared family (117 lines).
- **Deleted:** `_fragment_builder.py`, `_graph_taxonomy.py`, `_finding_builder.py`
  (the fabrication modules).
- `tests/cloudforge/learn/test_normalizer.py` — removed fabrication assertions; added
  `TestDeclaredFieldPreservation` + `TestDeclaredWeaknessFamilyPreservation` (incl.
  the S3 dedup-collision-resolved test); updated graph-fragment tests to assert the
  honest minimal fragment (no fabricated edges) + empty findings.
- `tests/cloudforge/learn/test_quality.py` — reverted the "derived-finding" premise
  fix (seeds are naturally finding-less now).

## Gates
- `ruff check app/ tests/ --fix` — **clean**
- `ruff format app/ tests/` — clean (117 files unchanged)
- `mypy --strict app/` — **Success, no issues in 62 files**
- `pytest tests/cloudforge/learn/ -q --no-cov` — **260 passed, 4 deselected**
- `pytest tests/cloudforge/ -q --no-cov` (bare default suite) — **376 passed, 9 deselected**
- All touched modules ≤200 lines (normalizer 187, _fragment 65, _taxonomy 117).
- Signed off. Never `--no-verify`.
