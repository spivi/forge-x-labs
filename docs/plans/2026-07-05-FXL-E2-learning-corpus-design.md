# FXL-E2 — Cloud Risk Pattern Learning Corpus (Design & Plan)

**Status**: Draft (planning)
**Epic**: FXL-E2
**Milestone**: E2 — Cloud Risk Pattern Learning Corpus
**Date**: 2026-07-05
**Author**: planning agent
**Related decisions**: FXL-D001 (`app/cloudforge/` layout), FXL-D002 (validators > generation
cleverness), FXL-D003 (12-point "validated" definition), FXL-D004 (harden before breadth)

> **This is a plan, not code.** It defines the pipeline, models, adapters, governance,
> package layout, CLI surface, testing strategy, docs, and build order for the learning
> corpus. Implementation is the work of the 18 child tickets tracked under this epic.

---

## 1. Mission & hard non-goals

### Mission

Build a **local-first learning-corpus pipeline** that teaches cloudforge what
"bad-but-realistic cloud environments" look like by **fetching → ingesting → normalizing →
validating → deduplicating → scoring → exporting** cloud-risk **patterns** from **approved**
public + local sources. It prepares the **DATA foundation** for future graph
generation / diffusion. The output is a **validated corpus of normalized `RiskPattern`s**,
each carrying provenance and a graph fragment compatible with the existing `ScenarioGraph`.

The guiding directive for the whole epic:

> **This epic is about DATA DISCIPLINE**, not ML: source registry, provenance,
> normalization, safety classification, deduplication, quality scoring, and training export.
> Internet fetching is allowed **only from an approved registry**. No broad crawling.

### Hard non-goals (verbatim exclusion list)

This epic **must NOT**:

- ❌ Train a model.
- ❌ Do diffusion / GNN / embeddings.
- ❌ Use Modal or any GPU.
- ❌ Run `terraform apply`, do a real cloud deploy, or use AWS credentials.
- ❌ Generate, ingest, or store exploit / offensive / operational-attack content.
- ❌ Do broad or GitHub-wide crawling. Internet fetching is **only** from the approved
  `source_registry.yaml`, never a scraper/spider.

Two governance rules restate the spirit:

- **"No provenance, no corpus."** A `RiskPattern` with no `PatternProvenance` fails corpus
  validation.
- **Unknown / restricted license → excluded from the training export by default.**
  **Unsafe-operational content → rejected outright.**

This mirrors the product's existing posture (README "What it is NOT", FXL-D002): defensive
research only, local-first, no creds, deterministic — the corpus pipeline inherits all of it.

---

## 2. The pipeline

```
                approved sources only (registry-gated)
                          │
   ┌──────────────────────▼───────────────────────────────────────────────┐
   │  source material  (local scenario dirs · local rule catalogs ·        │
   │                     approved public URLs · recorded fixtures)         │
   └──────────────────────┬───────────────────────────────────────────────┘
                          │  fetch (registry-gated, provenance-stamped)
                          ▼
   ┌──────────────────────────────────────────────────────────────────────┐
   │  raw cache   data/raw/<source_id>/<content_hash>  +  metadata.json    │  ← provenance born here
   └──────────────────────┬───────────────────────────────────────────────┘
                          │  adapter.extract()
                          ▼
   ┌──────────────────────────────────────────────────────────────────────┐
   │  RawPatternRecord   (adapter-specific, minimally structured)          │
   └──────────────────────┬───────────────────────────────────────────────┘
                          │  PatternNormalizer.normalize()
                          ▼
   ┌──────────────────────────────────────────────────────────────────────┐
   │  RiskPattern   (normalized ontology + graph_fragment + provenance)    │
   └──────────────────────┬───────────────────────────────────────────────┘
                          │  graph-fragment validation
                          ▼
   ┌──────────────────────────────────────────────────────────────────────┐
   │  validated fragment   (endpoints resolve · types known-or-generic ·   │
   │                        findings ref real resources · no forbidden acts)│
   └──────────────────────┬───────────────────────────────────────────────┘
                          │  deterministic dedup (merge provenance)
                          ▼
   ┌──────────────────────────────────────────────────────────────────────┐
   │  deduped corpus                                                        │
   └──────────────────────┬───────────────────────────────────────────────┘
                          │  quality + realism scoring
                          ▼
   ┌──────────────────────────────────────────────────────────────────────┐
   │  quality-scored corpus  (+ coverage summary: provider/domain/family)  │
   └──────────────────────┬───────────────────────────────────────────────┘
                          │  export gate (validated · training_eligible ·
                          │               safe classification · reuse allowed ·
                          │               quality_score ≥ 0.70)
                          ▼
   ┌──────────────────────────────────────────────────────────────────────┐
   │  training-ready export   (the DATA foundation for future diffusion)   │
   └──────────────────────────────────────────────────────────────────────┘
```

Every arrow is a small, testable module. Nothing here is an agentic runtime — it is a
deterministic ETL pipeline with a Typer CLI on top, in the same spirit as the existing
`generate → validate → report` flow.

---

## 3. Source tiers (research-backed) & reuse posture

Four tiers, ordered by how cleanly they map to cloud-risk patterns *and* how safe their reuse
is. **`metadata_only` sources are NOT training-eligible by default** — we extract IDs,
resource-types, and short summaries, and never copy rule source text.

### Tier 1 — Scanner rule corpora (structured cloud misconfig knowledge)

The richest, most directly-mappable knowledge of "bad cloud config", already
resource-typed and severity-tagged.

| Priority | Source | What we take | License / reuse posture | Training-eligible? |
|---|---|---|---|---|
| **1st** | **Checkov** Terraform policy index | Policy **IDs**, titles, resource types, severities, categories — **metadata only** from a recorded fixture HTML page | Apache-2.0 (permissive) **but** we still treat the index as `metadata_only`: extract IDs/resource-types/summaries, **never copy rule source/logic** | **No** (metadata_only default) |
| 2nd | Trivy misconfig checks | Same shape as Checkov | Apache-2.0 | metadata_only by default |
| later | Prowler checks | Same shape | Apache-2.0 | metadata_only by default |

> **Checkov is the concrete adapter in THIS epic** (`checkov_policy_index`), metadata-only,
> from a **recorded fixture** — no live Checkov/OPA install, no internet in unit tests.

### Tier 2 — Cloud-provider guidance (authoritative "here's what's risky")

| Priority | Source | What we take | Reuse posture |
|---|---|---|---|
| **1st** | **AWS IAM Access Analyzer** findings taxonomy | Finding categories → `weakness_family`, `missing_controls` | AWS docs — attribute; extract categories/summaries, `reuse_status: attribution` |
| later | AWS Well-Architected (Security pillar) | Control themes → `domains`, `missing_controls` | attribution |
| later | Azure / GCP security guidance | provider-specific families | attribution |

No adapter is *built* for Tier 2 in this epic — it is registry-scaffolded for the future.

### Tier 3 — Control frameworks (map patterns to controls)

| Priority | Source | What we take | Reuse posture | Training-eligible? |
|---|---|---|---|---|
| **1st** | **CSA Cloud Controls Matrix (CCM)** — 197 controls / 17 domains, machine-readable | Control IDs + domains → `control_mappings`, `missing_controls`, `domains` | **CSA reuse terms need a human call** — default `reuse_status: restricted`, `allowed_for_training: false` until confirmed | **No** (restricted default) |
| 1st | **CIS Benchmarks** | Benchmark **metadata only** (section IDs, titles) | CIS content is **restricted**; `metadata_only` + `restricted` | **No** |

> ⚠️ **Human call needed (coordinator):** CSA CCM and CIS reuse rights. Until a human
> confirms, both stay `restricted` / not-training-eligible. Control **mappings** (our IDs →
> their public control IDs) are fine; copying their control *text* is not.

### Tier 4 — Public "bad-env" IaC (realism sink)

| Source | Rule |
|---|---|
| Curated intentionally-vulnerable IaC repos (the kind used for scanner demos) | **LOCAL curated registry ONLY.** A human vets and pins specific commits into the registry. **No broad scraping, no spider, no GitHub-wide crawl.** Each entry carries its own license; unknown → not training-eligible. |

---

## 4. `data/source_registry.yaml` — schema & governance

The registry is the **allow-list**. The fetcher refuses anything not in it. A starter file
ships with this plan (see `data/source_registry.yaml`).

### Per-entry schema

```yaml
sources:
  - id: checkov-terraform-index          # stable slug, used in provenance + raw cache path
    name: "Checkov Terraform policy index"
    type: scanner_rule_index             # scanner_rule_index | scanner_rule_catalog |
                                         # provider_guidance | control_framework |
                                         # local_scenario_dir | local_rule_catalog | iac_repo
    url: "https://www.checkov.io/5.Policy%20Index/terraform.html"  # OR path: for local
    adapter: checkov_policy_index         # which adapter ingests it
    enabled: true
    license: "Apache-2.0"                 # SPDX id or "unknown"
    reuse_status: metadata_only           # full_reuse | attribution | metadata_only |
                                          # restricted | unknown
    allowed_for_training: false           # governance-derived (see rules below)
    notes: "Metadata only: IDs/resource-types/summaries. Never copy rule source."
```

### Governance rules (enforced by the registry loader + normalizer)

1. **`license: unknown` → `allowed_for_training: false`** (auto-forced, even if the file
   says true). Unknown provenance is never training data.
2. **`reuse_status: restricted` → excluded from the training export** (may still live in the
   corpus for analysis, but the export gate drops it).
3. **`reuse_status: metadata_only` → extract IDs / resource-types / summaries ONLY.** The
   adapter must never copy rule source, rule logic, or benchmark control text into a
   `RiskPattern`. `allowed_for_training: false` by default.
4. **`reuse_status: full_reuse` / `attribution` →** training-eligible *iff* the pattern is
   otherwise safe and validated; `attribution` requires provenance to carry the source name +
   URL (it always does).
5. **Unsafe-operational content → rejected** at classification (never enters the corpus).
6. **Raw cache layout:** every fetch writes
   `data/raw/<source_id>/<content_hash>` (the bytes) **and**
   `data/raw/<source_id>/<content_hash>.metadata.json` (fetched_at, url/path, source_id,
   content_hash, adapter, http status, etc.). The content hash makes the cache
   content-addressed and the fetch idempotent.

The **registry loader** validates each entry (pydantic), applies rules 1–2 to derive the
effective `allowed_for_training`, and refuses to hand the fetcher any `enabled: false` or
unlisted source.

---

## 5. `app/cloudforge/learn/` package layout

Small modules, existing repo style (compare `validate/`, `generate/`), functions ≤30 lines /
modules ≤200 (rules/general.md). **This is an ETL library + CLI, NOT an agentic runtime.**

```
app/cloudforge/learn/
├── __init__.py
├── cli.py                 # Typer command group wired into app.cloudforge.cli
├── pattern_models.py      # RiskPattern, PatternProvenance, RawPatternRecord, enums
├── source_models.py       # SourceEntry, SourceRegistry, RawCacheMetadata, enums
├── registry.py            # load + validate source_registry.yaml; apply governance rules
├── fetch.py               # registry-gated fetcher → data/raw/<id>/<hash> + metadata.json
├── adapters/
│   ├── __init__.py
│   ├── base.py            # PatternAdapter protocol: extract() -> list[RawPatternRecord]
│   ├── cloudforge_scenario.py   # ingest existing out/ scenario dirs
│   ├── rule_catalog_yaml.py     # ingest local curated rule catalog (seed patterns)
│   └── checkov_policy_index.py  # METADATA-ONLY from recorded fixture HTML
├── normalizer.py          # RawPatternRecord -> RiskPattern (+ graph_fragment)
├── validate.py            # graph-fragment validation rules
├── dedup.py               # deterministic dedup (key + merge provenance)
├── quality.py             # quality + realism scoring
├── corpus.py              # load/save corpus; corpus-level validation checks
├── export.py              # training-export gate + writer
└── summarize.py           # coverage summary (provider/domain/family)
```

Adapters live in a sub-package because they will grow (Trivy, Prowler, provider guidance)
without bloating `learn/`. Everything reuses `app.cloudforge.models.graph` for the fragment
and `app.cloudforge.errors.CloudforgeError` for failures.

---

## 6. The `RiskPattern` ontology

A `RiskPattern` is the normalized unit of the corpus. It is **compatible with the existing
`ScenarioGraph`**: `graph_fragment` is a `ScenarioGraph` (or a nodes/edges pair that
constructs one) using the existing `NodeType` / `EdgeType` / `GraphNode` / `GraphEdge`.

### Fields

| Field | Type | Notes |
|---|---|---|
| `id` | `str` | stable slug, e.g. `s3-public-read-aws-001` |
| `title` | `str` | short human title |
| `summary` | `str` | 1–3 sentence description of the risk |
| `cloud_provider` | `CloudProvider` enum | see below |
| `domains` | `list[Domain]` | see below |
| `weakness_family` | `WeaknessFamily` enum | see below |
| `severity` | `Severity` (`low`/`medium`/`high`/`critical`) | reuse existing `Severity` |
| `affected_resource_types` | `list[str]` | e.g. `["aws_s3_bucket"]` (normalized, sorted) |
| `risky_relationships` | `list[str]` | edge-type semantics, e.g. `["can_pass_role"]` |
| `missing_controls` | `list[str]` | controls that SHOULD exist but don't |
| `negative_controls` | `list[str]` | controls actively misconfigured (e.g. public ACL) |
| `compensating_controls` | `list[str]` | controls that reduce the risk (benign-FP signal) |
| `graph_fragment` | `ScenarioGraph` | **reuses existing graph model** — nodes+edges |
| `expected_findings` | `list[ExpectedFinding]` | reuse existing findings model |
| `remediation` | `str` | how to fix |
| `detection_hints` | `list[str]` | what a scanner would look for |
| `control_mappings` | `list[str]` | our IDs → external control IDs (CCM/CIS/etc.) |
| `source_mappings` | `list[str]` | external rule IDs (e.g. Checkov `CKV_AWS_20`) |
| `provenance` | `PatternProvenance` | **required — no provenance, no corpus** |
| `confidence` | `float` | 0..1, adapter-defaulted (see §8) |
| `realism_score` | `float` | 0..1, scored by `quality.py` |
| `quality_score` | `float` | 0..1, scored by `quality.py` |
| `validation_status` | `ValidationStatus` | `unvalidated`/`valid`/`invalid` |
| `safety_classification` | `SafetyClassification` enum | see below |
| `training_eligible` | `bool` | derived: safe class + reuse-allowed + validated |

### Enums

- **`cloud_provider`**: `aws` · `azure` · `gcp` · `kubernetes` · `multi_cloud` · `generic`
- **`domains`** (multi): `iam` · `storage` · `network` · `logging` · `encryption` · `ci_cd` ·
  `secrets` · `data` · `compute` · `database` · `serverless` · `containers` · `monitoring` ·
  `governance`
- **`weakness_family`**: the **cloudforge families**
  (`iam_excessive_privilege`, `iam_passrole_risk`, `s3_logging_missing`, `s3_public_exposure`,
  `security_group_overexposed`, `public_looking_bucket_with_compensating_control` — reuse
  `models.findings.FindingFamily`) **plus a generic list**:
  `public_exposure`, `excessive_privilege`, `missing_encryption`, `missing_logging`,
  `weak_network_boundary`, `insecure_defaults`, `secrets_exposure`, `unrestricted_access`,
  `misconfigured_control`, `other`.
- **`safety_classification`**: `defensive_pattern` · `benchmark_pattern` · `training_pattern`
  · `restricted_source` · `unsafe_operational` · `unknown`

### Training-eligibility rule

`training_eligible` is **derived**, not free-form. The **training export excludes**
`restricted_source`, `unsafe_operational`, and `unknown` classifications **unless a CLI flag
overrides** (`--include-restricted`, off by default, and it still never includes
`unsafe_operational`). A pattern is training-eligible iff:

```
validation_status == valid
AND safety_classification in {defensive_pattern, benchmark_pattern, training_pattern}
AND provenance.allowed_for_training == true
AND provenance.reuse_status not in {restricted, metadata_only, unknown}
```

---

## 7. `PatternProvenance` model

**Rule: no provenance → corpus validation fails.** Every `RiskPattern` carries exactly one.

| Field | Type | Notes |
|---|---|---|
| `source_id` | `str` | registry id |
| `source_name` | `str` | human name |
| `source_type` | `str` | registry `type` |
| `source_url_or_path` | `str` | where it came from |
| `source_license` | `str` | SPDX or `unknown` |
| `reuse_status` | `ReuseStatus` | `full_reuse`/`attribution`/`metadata_only`/`restricted`/`unknown` |
| `allowed_for_training` | `bool` | governance-derived (registry §4) |
| `extraction_method` | `str` | e.g. `fixture_html_metadata`, `scenario_dir`, `yaml_catalog` |
| `fetched_at` | `datetime` | when the raw cache was written |
| `extracted_at` | `datetime` | when the adapter ran |
| `content_hash` | `str` | of the raw cached bytes |
| `adapter_name` | `str` | which adapter |
| `adapter_version` | `str` | pin for reproducibility |
| `normalizer_version` | `str` | pin for reproducibility |
| `confidence` | `float` | adapter default carried through |
| `notes` | `str` | free text (e.g. "metadata only; rule source not copied") |

---

## 8. The 3 adapters for THIS epic

All implement a common `PatternAdapter` protocol (`adapters/base.py`):
`extract(source, raw) -> list[RawPatternRecord]`. Each stamps its `adapter_name` /
`adapter_version` into provenance.

| # | Adapter | Source | Extraction | `confidence` default | `training_eligible` default |
|---|---|---|---|---|---|
| 1 | **`cloudforge_scenario`** | existing `out/` scenario dirs (`scenario.yaml` / `graph.json` / `expected_findings.json` / `ground_truth_paths.json`) | read the graph + findings directly; they are already validated and self-consistent | **0.85** | **true** |
| 2 | **`rule_catalog_yaml`** | a LOCAL curated YAML catalog (the seed patterns, Tier 4 local registry) | parse each catalog entry into a `RawPatternRecord` | **0.75** | **true** |
| 3 | **`checkov_policy_index`** | **recorded fixture HTML** of the Checkov Terraform policy index | **METADATA ONLY**: policy IDs, resource types, titles, severities. **Never copy rule source.** | **0.55** | **false** (metadata_only) |

### Seed rule catalog (`rule_catalog_yaml` input)

Ships **≥12 seed `RiskPattern`s**, an **AWS / Azure / GCP mix**, spanning the domains
(iam, storage, network, logging, encryption, ci_cd, secrets, data). Each seed is
hand-authored, `defensive_pattern`, with a valid `graph_fragment` and provenance
(`source_id: local-rule-catalog`, `reuse_status: full_reuse`, `allowed_for_training: true`).
These are the corpus's dependable core.

---

## 9. Normalizer, fragment validation, dedup, quality, export

### 9.1 Normalizer responsibilities (`normalizer.py`)

`RawPatternRecord → RiskPattern`:

- Map adapter-specific fields onto the ontology (§6); normalize resource types, sort list
  fields for determinism.
- Build/verify the `graph_fragment` as a real `ScenarioGraph` (reusing the existing model —
  its `model_validator` already checks edge endpoints resolve).
- Assign `safety_classification` from the source's `reuse_status` + a content scan:
  `metadata_only` → `benchmark_pattern`/`restricted_source` as appropriate; anything matching
  the unsafe-operational content scan → `unsafe_operational` (rejected).
- Stamp provenance completely (fail if incomplete). Set `confidence` from the adapter default.
- Set `validation_status = unvalidated` (the validator sets `valid`/`invalid`).
- Pin `normalizer_version`.

### 9.2 Graph-fragment validation rules (`validate.py`)

A fragment is valid only if:

1. **Endpoints resolve** — every edge `from`/`to` references a node in the fragment (the
   existing `ScenarioGraph` validator enforces this; we surface it here explicitly).
2. **Node/edge types are known-or-generic** — a type is either in the existing
   `NodeType`/`EdgeType` enums, or explicitly a documented generic placeholder. Unknown,
   undocumented types fail.
3. **Findings reference existing resources** — every `ExpectedFinding.resource_ids` points to
   a node in the fragment (mirrors FXL-D003 point 4).
4. **No forbidden destructive actions** — reuse `constants.FORBIDDEN_PERMISSION_PATTERNS`
   (`iam:Delete*`, `s3:DeleteBucket`, `ec2:TerminateInstances`, `kms:ScheduleKeyDeletion`,
   `organizations:*`); any policy content matching these fails and marks the pattern
   `unsafe_operational` → rejected. (Broad *read* grants are allowed, as in the generator.)

`validation_status` becomes `valid` only when all four pass.

### 9.3 Deterministic dedup (`dedup.py`)

Two patterns are duplicates iff their **dedup key** matches. The key is deterministic:

```
key = (
    cloud_provider,
    weakness_family,
    tuple(sorted(affected_resource_types)),
    tuple(sorted(risky_relationships)),
    tuple(sorted(missing_controls)),
    tuple(sorted(compensating_controls)),
)
```

On a collision: **keep the highest-`quality_score`** pattern; **merge the provenance** of the
dropped duplicates into the survivor (a `duplicate_provenances` list or merged
`source_mappings`); **record the dropped `duplicate_ids`** on the survivor. Deterministic —
same input corpus → same survivors. No fuzzy matching, no embeddings (that would be ML).

### 9.4 Quality & realism scoring (`quality.py`)

Deterministic, rubric-based (NOT learned). Dimensions (each 0..1, weighted into
`quality_score`; realism is its own `realism_score`):

- **Provenance completeness** — all required provenance fields present.
- **Fragment richness** — ≥2 nodes and ≥1 edge; more structure scores higher.
- **Findings coverage** — has ≥1 `ExpectedFinding` referencing the fragment.
- **Control mapping** — has `control_mappings` and/or `missing_controls`.
- **Realism** (`realism_score`) — plausible resource-type + relationship + severity
  combination; penalize incoherent combos.
- **Confidence** — the adapter confidence carried through.

`export.py` uses `quality_score ≥ 0.70` as the export bar (§9.6).

### 9.5 Corpus validation checks (`corpus.py`)

Corpus-level gate (mirrors the scenario 12-point discipline of FXL-D003):

- Every pattern has complete provenance (**no provenance, no corpus**).
- Every pattern's `graph_fragment` passes fragment validation.
- No two patterns share an `id`.
- No `unsafe_operational` pattern is present (they must have been rejected upstream).
- `safety_classification` and `training_eligible` are internally consistent with provenance.
- Enums are in-vocabulary.

### 9.6 Training-export rules (`export.py`)

A pattern is written to the training export **only if ALL** hold:

```
validation_status == valid
AND training_eligible == true
AND safety_classification in {defensive_pattern, benchmark_pattern, training_pattern}
AND provenance.reuse_status allows reuse (full_reuse or attribution)
AND provenance.allowed_for_training == true
AND quality_score >= 0.70
```

`restricted_source` / `unsafe_operational` / `unknown` are **excluded**. A CLI
`--include-restricted` flag can override the `restricted_source` exclusion for local
analysis, but **never** includes `unsafe_operational`, and the export records that the flag
was used. The export format is a versioned JSONL/JSON bundle with a manifest (counts,
provider/domain/family coverage, the export ruleset used).

---

## 10. CLI surface — `cloudforge learn`

The existing CLI is **Typer**. Recommendation: a **nested `learn` sub-command group** added to
`app.cloudforge.cli.app` (`app.add_typer(learn_app, name="learn")`), keeping the top-level
`generate`/`validate`/`report` untouched. **Fallback:** if nesting is awkward with the current
Typer wiring, ship **flat commands** (`cloudforge learn-fetch-sources`, …) instead — same
behavior, uglier surface.

| Command | Does |
|---|---|
| `cloudforge learn fetch-sources` | Fetch every `enabled` registry source into `data/raw/` (registry-gated, provenance-stamped). |
| `cloudforge learn ingest --adapter <name>` | Run one adapter over its cached raw sources → normalized `RiskPattern`s appended to the corpus. |
| `cloudforge learn validate-corpus` | Run corpus + fragment validation; print PASS/WARN/FAIL like `validate`. |
| `cloudforge learn summarize` | Print coverage summary (provider / domain / family counts, quality distribution). |
| `cloudforge learn export-training [--include-restricted]` | Apply the export gate; write the training bundle + manifest. |

All commands are thin — they call `learn/` modules and print with `rich`, matching `cli.py`.

---

## 11. Testing strategy

- **Unit tests need NO internet / terraform / checkov / opa / creds.** Everything runs off
  **recorded fixtures**: a fixture Checkov policy-index HTML, a fixture local rule catalog, a
  fixture `out/` scenario dir. This mirrors the repo's existing fail-soft, tool-optional
  testing posture.
- **Internet integration tests** (actually hitting an approved registry URL) live behind a
  **`pytest -m internet` marker, registered in `pyproject.toml` / `pytest.ini`, and skipped
  by default**. CI and local `pytest` never touch the network unless `-m internet` is passed
  explicitly. (Same pattern as the terraform/opa presence-gated tests.)
- Determinism tests: same input corpus → identical dedup survivors and identical export bytes.
- Coverage stays ≥80% on `app` (rules/testing.md); the new `learn/` package pulls its weight.
- `ruff` + `mypy --strict` clean.

---

## 12. Docs (7 wiki pages + README)

Add to `docs/wiki/` (mirrored to the GitHub Wiki) and link from `Home.md`:

1. **`Learning-Corpus.md`** — the pipeline, the mission, the non-goals, how to run it.
2. **`Source-Registry.md`** — the registry schema + governance rules + how to add a source.
3. **`Risk-Pattern-Ontology.md`** — the `RiskPattern` fields + enums + graph-fragment compat.
4. **`Source-Adapters.md`** — the adapter protocol + the 3 adapters + how to add one.
5. **`Provenance-and-Licensing.md`** — provenance model, "no provenance no corpus", the
   license/reuse postures, the CSA/CIS human-call caveat.
6. **`Corpus-Quality-Scoring.md`** — dedup key, quality/realism dimensions, export gate.
7. **`Future-Diffusion-Training.md`** — how this corpus feeds future diffusion **without**
   implementing it (see §14).

Plus a **README** section ("Learning corpus") summarizing the pipeline and pointing at the
wiki, consistent with the existing README voice.

---

## 13. Build order & effort

Dependency-ordered. Each maps to a child ticket (see §15). Effort in S/M/L (per the repo's
S = 1–2 files, M = 3–5, L = 6+).

| Order | Ticket | Effort | Why here |
|---|---|---|---|
| 1 | #3 RiskPattern + provenance models | **M** | Everything depends on the ontology. |
| 2 | #1 source registry model + file | **S** | The allow-list + governance rules. |
| 3 | #4 learn package structure | **S** | Skeleton so later tickets have homes. |
| 4 | #2 raw source fetcher + cache | **M** | Registry-gated fetch → provenance is born. |
| 5 | #5 rule catalog YAML adapter | **M** | First adapter; unblocks seeds. |
| 6 | #6 cloudforge scenario adapter | **M** | Reuses existing out/ dirs. |
| 7 | #7 checkov policy index adapter | **M** | Metadata-only, fixture-driven. |
| 8 | #8 PatternNormalizer | **M** | Needs adapters producing RawPatternRecords. |
| 9 | #9 graph-fragment validation | **M** | Needs normalized fragments. |
| 10 | #10 deterministic dedup | **M** | Needs validated patterns. |
| 11 | #11 quality scoring | **M** | Needs deduped corpus. |
| 12 | #12 corpus validation | **M** | Needs the full pattern set. |
| 13 | #13 training export | **M** | The export gate — needs quality + validation. |
| 14 | #14 seed rule catalog (≥12) | **M** | Data, authored once the catalog adapter exists. |
| 15 | #15 learn CLI commands | **M** | Wires the pipeline to the user. |
| 16 | #16 internet-marked integration tests | **S** | Opt-in, after the fetcher + adapters. |
| 17 | #17 docs: registry + provenance | **S** | Doc the governance surface. |
| 18 | #18 docs: future diffusion | **S** | Doc the future without building it. |

> Rough ordering, not a hard chain: #14 (seeds) can be authored as soon as #5 lands; docs
> (#17/#18) can start once the models (#3/#1) stabilize.

---

## 14. Prepares future diffusion WITHOUT implementing it

This epic **stops at the DATA**. It deliberately builds the foundation a future
diffusion/graph-generation effort would need, and no further:

- **What it provides:** a validated, deduped, quality-scored, provenance-complete set of
  normalized `RiskPattern`s whose `graph_fragment`s are already in the product's own
  `ScenarioGraph` vocabulary — i.e. training-ready graphs with ground truth and labels.
- **What it does NOT do:** no embeddings, no tokenizer, no GNN, no diffusion model, no
  training loop, no GPU, no Modal. The `export-training` command writes a *dataset*, not a
  *model*.
- **The seam:** a future `DiffusionGraphGenerator` (already documented as a future engine in
  the Roadmap / Modal-and-Diffusion wiki) would *consume* this export and *emit* candidate
  `ScenarioGraph`s — which then go straight back through the **existing local validators**
  (FXL-D002: validators remain the source of truth, regardless of the generation engine).
- **Invariant preserved:** exactly as with `TemplateGenerator`/`MutationGenerator`, a
  generated graph is only trustworthy once the risk engine (and, where available,
  checkov/OPA) validate it. The corpus makes better *proposals* possible; it never outranks
  validation.

`Future-Diffusion-Training.md` documents this seam so the boundary is explicit and the epic
cannot quietly drift into ML.

---

## 15. The 18 child tickets

1. Add source registry model and file — **S**
2. Add raw source fetcher and cache — **M**
3. Define RiskPattern and provenance models — **M**
4. Add learning package structure — **S**
5. Implement rule catalog YAML adapter — **M**
6. Implement cloudforge scenario adapter — **M**
7. Implement Checkov policy index adapter (metadata-only) — **M**
8. Implement PatternNormalizer — **M**
9. Implement graph fragment validation — **M**
10. Implement deterministic dedup — **M**
11. Implement quality scoring — **M**
12. Implement corpus validation — **M**
13. Implement training export — **M**
14. Add seed rule catalog (≥12 patterns) — **M**
15. Add learn CLI commands — **M**
16. Add internet-marked integration tests — **S**
17. Add docs for source registry and provenance — **S**
18. Add docs for future diffusion training — **S**

---

## 16. Acceptance criteria (epic)

1. `data/source_registry.yaml` exists with the schema in §4 and the two starter entries
   (checkov-terraform-index metadata-only; local-rule-catalog full-reuse).
2. Registry loader enforces governance: `unknown` license → not training-eligible;
   `restricted` → excluded from export; `metadata_only` → IDs/summaries only.
3. Fetcher is **registry-gated** (refuses unlisted/disabled sources), writes
   `data/raw/<source_id>/<content_hash>` + `metadata.json`, and is idempotent.
4. `RiskPattern` + `PatternProvenance` models exist with the full field list & enums (§6/§7),
   and `graph_fragment` is a real `ScenarioGraph` reusing the existing node/edge model.
5. **No provenance → corpus validation fails** is enforced and tested.
6. Three adapters land (`cloudforge_scenario`, `rule_catalog_yaml`, `checkov_policy_index`)
   with the specified confidence (0.85/0.75/0.55) and training-eligibility (true/true/false)
   defaults; the Checkov adapter is metadata-only and copies **no** rule source.
7. Normalizer produces valid, deterministic `RiskPattern`s (sorted fields, pinned versions).
8. Graph-fragment validation enforces the 4 rules (§9.2), including no forbidden actions.
9. Deterministic dedup uses the specified key, keeps highest quality, merges provenance,
   records `duplicate_ids`; same input → same survivors.
10. Quality scoring is deterministic and rubric-based; realism scored separately.
11. Corpus validation gate passes only a self-consistent, provenance-complete corpus.
12. Training export excludes `restricted_source`/`unsafe_operational`/`unknown` and anything
    with `quality_score < 0.70`, unless `--include-restricted` (which still never includes
    `unsafe_operational`).
13. ≥12 seed patterns ship (AWS/Azure/GCP mix, domain spread), all valid & training-eligible.
14. `cloudforge learn` CLI exposes fetch-sources / ingest / validate-corpus / summarize /
    export-training.
15. Unit tests need no internet/terraform/checkov/opa/creds (fixtures); internet tests are
    behind `-m internet`, skipped by default; `ruff` + `mypy --strict` clean; coverage ≥80%.
16. The 7 wiki pages + README section land and document the governance + the
    prepares-diffusion-without-implementing-it boundary.

---

## 17. Risks & open questions (coordinator)

- **CSA CCM & CIS reuse rights — human call required.** Defaulted to `restricted` /
  not-training-eligible until a human confirms. Control **mappings** (our IDs → their public
  control IDs) are safe; copying their control **text** is not. Do not upgrade these to
  training-eligible without an explicit decision (record it as an FXL-D decision).
- **Checkov index is `metadata_only` even though Apache-2.0** — chosen conservatively so the
  epic never copies rule logic. If a human later approves fuller reuse, that is a registry
  edit + a decision, not a code change.
- **Tier-4 IaC repos** are local-registry-only by policy; the "no broad crawl" rule must be
  enforced in the fetcher (it only fetches registry entries), not just documented.
- **Nested-vs-flat CLI** — recommend nested `learn` group; fall back to flat if Typer wiring
  fights it. Non-blocking.
