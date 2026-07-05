# Learning Corpus

> **Epic FXL-E2.** This epic is about **data discipline**, not ML. It builds the data
> foundation a *future* graph-generation/diffusion effort would need — it does not train
> anything. See [Future Diffusion Training](Future-Diffusion-Training) for the boundary.

## What it is

The learning corpus is a **local-first ETL pipeline** that teaches cloudforge what
"bad-but-realistic cloud environments" look like by fetching, ingesting, normalizing,
validating, deduplicating, scoring, and exporting cloud-risk **patterns** from approved
public and local sources. The output is a validated corpus of normalized `RiskPattern`s
(see [Risk Pattern Ontology](Risk-Pattern-Ontology)), each carrying provenance
(see [Provenance and Licensing](Provenance-and-Licensing)) and a `graph_fragment`
compatible with the product's existing `ScenarioGraph` (see [Graph Model](Graph-Model)).

## The pipeline

```
approved sources only (registry-gated, see Source Registry)
        │
        ▼ fetch                    data/raw/<source_id>/<content_hash> + metadata.json
        │                          (provenance is born here)
        ▼ adapter.extract()        RawPatternRecord (adapter-specific, minimally structured)
        │
        ▼ normalize                RiskPattern (ontology + graph_fragment + provenance)
        │
        ▼ validate fragment        endpoints resolve · types known-or-generic ·
        │                          findings reference real resources · no forbidden actions
        ▼ dedup                    deterministic key match; merge provenance; keep best
        │
        ▼ score                    quality + realism scoring (rubric-based, not learned)
        │
        ▼ export gate              validated · training_eligible · safe · reuse-allowed ·
        │                          quality_score >= 0.70
        ▼
training-ready export     (the DATA foundation for a future diffusion effort)
```

Every arrow is a small, testable module under `app/cloudforge/learn/` (see the package
layout below). This is a deterministic ETL library with a Typer CLI on top — **not** an
agentic runtime — in the same spirit as the existing `generate → validate → report` flow.

## Status: what's built vs. what's planned

The models, registry, fetcher, and three adapters are merged on `master`. The rest of the
pipeline (normalize → validate → dedup → score → export) and the CLI are **design intent,
not yet implemented** — each stub module documents its own ticket:

| Stage | Module | Status | Ticket |
|---|---|---|---|
| Source registry (allow-list) | `learn/source_models.py`, `learn/registry.py` | Built | #58/#59 |
| Fetcher + raw cache | `learn/fetch.py` | Built | #60 |
| Ontology (`RiskPattern`, `PatternProvenance`) | `learn/pattern_models.py`, `learn/pattern_enums.py` | Built | #61 |
| Package skeleton | `learn/` layout | Built | #62 |
| `rule_catalog_yaml` adapter | `learn/adapters/rule_catalog_yaml.py` | Built | #63 |
| `cloudforge_scenario` adapter | `learn/adapters/cloudforge_scenario.py` | Built | #64 |
| `checkov_policy_index` adapter | `learn/adapters/checkov_policy_index.py` | Built | #65 |
| `PatternNormalizer` | `learn/normalizer.py` | Stub — design intent only | #66 |
| Graph-fragment validation | `learn/validate.py` | Stub — design intent only | #67 |
| Deterministic dedup | `learn/dedup.py` | Stub — design intent only | #68 |
| Quality + realism scoring | `learn/quality.py` | Stub — design intent only | #69 |
| Corpus validation gate | `learn/corpus.py` | Stub — design intent only | #70 |
| Training export gate | `learn/export.py` | Stub — design intent only | #71 |
| Seed rule catalog (>=12 patterns) | `data/rule_catalog/seed_patterns.yaml` | Not yet authored | #72 |
| `cloudforge learn` CLI | `learn/cli.py`, `learn/summarize.py` | Stub — design intent only | #73 |
| Internet-marked integration tests | `tests/cloudforge/learn/` | Not yet added | #74 |

Until the CLI (#73) lands, there is no `cloudforge learn ...` command to run — the pipeline
stages above the adapters are read-only design, not runnable code.

## Package layout (`app/cloudforge/learn/`)

```
app/cloudforge/learn/
├── cli.py                       Typer command group (stub, #73)
├── pattern_models.py             RiskPattern, PatternProvenance, RawPatternRecord
├── pattern_enums.py               CloudProvider, Domain, WeaknessFamily, SafetyClassification, ...
├── source_models.py               SourceEntry, SourceRegistry, RawCacheMetadata, ReuseStatus
├── registry.py                    load_registry() — parses + governs data/source_registry.yaml
├── fetch.py                       registry-gated fetcher -> data/raw/<id>/<hash> + metadata.json
├── adapters/
│   ├── base.py                    PatternAdapter protocol
│   ├── cloudforge_scenario.py     ingest existing out/ scenario dirs
│   ├── rule_catalog_yaml.py       ingest local curated rule catalog
│   └── checkov_policy_index.py    metadata-only, from a recorded fixture
├── normalizer.py                  stub (#66)
├── validate.py                    stub (#67)
├── dedup.py                       stub (#68)
├── quality.py                     stub (#69)
├── corpus.py                      stub (#70)
├── export.py                      stub (#71)
└── summarize.py                   stub (#73)
```

Adapters live in a sub-package because they will grow (Trivy, Prowler, provider guidance)
without bloating `learn/`. Everything reuses `app.cloudforge.models.graph` for the
fragment and `app.cloudforge.errors.CloudforgeError` for failures — the same conventions
as the rest of the product (see [Architecture](Architecture)).

## What it does NOT do (non-goals)

This epic's non-goal list is verbatim from the design and enforced throughout:

- **Does not train a model.** No diffusion, no GNN, no embeddings, no training loop.
- **Does not use Modal or any GPU.**
- **Does not run `terraform apply`, deploy to a real cloud, or use AWS credentials.**
- **Does not generate, ingest, or store exploit / offensive / operational-attack content.**
  Unsafe-operational content is rejected at classification, never enters the corpus.
- **Does not crawl the internet.** Fetching is allow-list-only, registry-gated — never a
  scraper or spider. See [Source Registry](Source-Registry).

Two governance rules restate the spirit and are enforced by the models/loader, not just
documented:

- **"No provenance, no corpus."** A `RiskPattern` with no `PatternProvenance` fails corpus
  validation.
- **Unknown or restricted license -> excluded from the training export by default.**
  See [Provenance and Licensing](Provenance-and-Licensing).

This mirrors the product's existing posture ([Safety & Scope](Safety-and-Scope)): defensive
research only, local-first, no credentials, deterministic — the corpus pipeline inherits
all of it.

## How it prepares future diffusion without implementing it

The corpus is designed as the **DATA foundation** a future graph-generation/diffusion
engine would consume — nodes, edges, findings, and quality scores all in the product's own
`ScenarioGraph` vocabulary, so a future generator's output could be validated by the same
local validators that already exist. No diffusion, GNN, embedding, or training code is part
of this epic. See [Future Diffusion Training](Future-Diffusion-Training) for the full
argument and the seam where a future engine would plug in.

## Related pages

- [Source Registry](Source-Registry) — the allow-list schema and governance rules.
- [Risk Pattern Ontology](Risk-Pattern-Ontology) — the `RiskPattern` fields and enums.
- [Source Adapters](Source-Adapters) — the three shipped adapters and the adapter protocol.
- [Provenance and Licensing](Provenance-and-Licensing) — the provenance model and reuse rules.
- [Corpus Quality Scoring](Corpus-Quality-Scoring) — the (planned) scoring dimensions.
- [Future Diffusion Training](Future-Diffusion-Training) — the future seam, not built here.
