# FXL-75 result — Learning-corpus governance docs

**Status**: Done — PR open, not merged (per instructions).
**PR**: https://github.com/spivi/forge-x-labs/pull/87 (branch `docs/FXL-75-corpus-docs` -> `master`)
**Closes**: #75

## Pages created (docs/wiki/)

1. `Learning-Corpus.md` — overview: mission, pipeline diagram
   (fetch→ingest→normalize→validate→dedup→score→export), a built-vs-stub status table
   (with real issue numbers), package layout, non-goals, and the future-diffusion seam.
2. `Source-Registry.md` — `data/source_registry.yaml` schema, `SourceType`/`ReuseStatus`
   enums, the 5 governance rules enforced by `registry.load_registry`, the 4 source tiers,
   and a description of the actual 4 entries shipped on master.
3. `Risk-Pattern-Ontology.md` — full `RiskPattern` field table, all enums
   (`CloudProvider`/`Domain`/`WeaknessFamily`/`SafetyClassification`/`ValidationStatus`),
   the derived `training_eligible` computed field, and `RawPatternRecord`.
4. `Source-Adapters.md` — the `PatternAdapter` protocol + the 3 shipped adapters
   (`cloudforge_scenario`/`rule_catalog_yaml`/`checkov_policy_index`) with their actual
   confidence defaults (0.85/0.75/0.55) and training-eligibility defaults (true/true/false).
5. `Provenance-and-Licensing.md` — `PatternProvenance` fields, the full `reuse_status`
   vocabulary (incl. `mappings_only`), governance enforcement (twice: loader + computed
   field), and FXL-D007 (CSA CCM mappings training-eligible, control text not; CIS stays
   restricted).
6. `Corpus-Quality-Scoring.md` — quality/realism dimensions, the dedup key, the export gate
   — explicitly framed as design intent (scorer lands in #69), not implemented code.
7. `Future-Diffusion-Training.md` — the future-diffusion seam (`DiffusionGraphGenerator`
   would consume the corpus's export and emit candidate graphs re-validated by existing
   local validators), and an explicit non-goal list (no embeddings/tokenizer/GNN/diffusion/
   training loop/GPU/Modal — no model trained in this epic).

Also updated `docs/wiki/Home.md` to link all 7 new pages from the page index.

## README

Added a "Learning corpus (FXL-E2)" section covering: what it does (allow-list fetch,
typed adapters, normalize/validate/dedup/score, export gate), what it does NOT do (no
training/diffusion/GNN/embeddings/Modal/GPU, no crawling, no offensive content), source
governance (license/reuse_status -> allowed_for_training rules), training-export rules
(validated + safe + licensed + quality_score >= 0.70), and example `cloudforge learn`
commands (noted as not-yet-runnable, CLI lands in #73).

## Grounding in current master (not overclaiming)

Read the design doc in full (`docs/plans/2026-07-05-FXL-E2-learning-corpus-design.md`),
`.dev-context/DECISIONS.md` (FXL-D003, FXL-D007), all existing `docs/wiki/*.md` for house
style, and the merged code: `source_models.py`, `pattern_enums.py`, `pattern_models.py`,
`registry.py`, `fetch.py`, `adapters/base.py`, all 3 adapters, and confirmed via
`gh issue list` that normalizer/validate/dedup/quality/corpus/export/summarize/cli.py are
literal stub files (docstring-only, "Implemented in ticket #NN") — verified real issue
numbers (#66 normalizer, #67 validate, #68 dedup, #69 quality, #70 corpus, #71 export, #72
seed catalog, #73 CLI, #74 internet tests) rather than trusting the design doc's own
(different, earlier) numbering scheme. Also confirmed `data/rule_catalog/seed_patterns.yaml`
does not exist yet (ticket #72 open) and the actual `data/source_registry.yaml` ships 4
entries (checkov-terraform-index enabled, local-rule-catalog enabled, local-scenarios-out
disabled, csa-ccm + cis-benchmarks disabled/scaffolded).

Every doc that mentions an unbuilt stage explicitly says "stub" / "design intent" / "not
yet implemented" and cites its tracking issue — no unbuilt piece (normalizer, dedup,
quality scorer, corpus validator, export gate, CLI, seed catalog) is described as existing
or runnable.

## Acceptance criteria coverage

- [x] All 7 docs/wiki pages exist, accurate to design + current master, in house doc voice
      (mirrors Architecture.md/Safety-and-Scope.md/Modal-and-Diffusion... structure: short
      sections, code fences, "Related pages" footers).
- [x] README has a Learning Corpus section covering what it does / doesn't do / example
      commands / source governance / training-export rules.
- [x] Explicit: allow-list-only fetching, no broad crawling, unknown/restricted excluded
      from training export by default, future diffusion depends on this corpus, no model
      trained here.
- [x] Intra-wiki links use extensionless page names (verified against existing pages'
      convention, e.g. `[Architecture](Architecture)`).

## CI status

Docs-only change. `gh pr checks 87` — all checks passed (0 failed), confirmed after the
initial pending set drained. Sanity test run before pushing:
`PYTHONPATH=. .venv/bin/pytest tests/cloudforge/ -q --no-cov -m 'not stress'` ->
213 passed, 1 skipped, 5 deselected, no regressions (only docs/README touched).

## Blockers

None. PR #87 is open and green, awaiting human merge decision (not merged, per
instructions).
