# Source Registry

`data/source_registry.yaml` is the **allow-list** for the learning corpus. It is the
**only** set of sources the fetcher and adapters are permitted to touch. There is **no
broad crawling and no spider** — the fetcher refuses anything not listed in this file, and
anything listed with `enabled: false`.

Models: `app/cloudforge/learn/source_models.py` (`SourceEntry`, `SourceRegistry`,
`RawCacheMetadata`, `ReuseStatus`, `SourceType`). Loader: `app/cloudforge/learn/registry.py`
(`load_registry`).

## Registry-only fetching, no crawling

The fetcher (`learn/fetch.py`) only ever requests the exact `url` values present in the
registry — there is no link-following, no search, no GitHub-wide scraping. Local `path`
sources never touch the network at all. Tier-4 "bad-env" IaC-style sources are, by policy,
**local-curated-registry only**: a human vets and pins entries; the fetcher enforces the
allow-list mechanically, it isn't just a documentation promise.

## Per-entry schema

```yaml
sources:
  - id: checkov-terraform-index          # stable slug; used in provenance + raw-cache path
    name: "Checkov Terraform policy index"
    type: scanner_rule_index             # see SourceType below
    url: "https://www.checkov.io/5.Policy%20Index/terraform.html"   # OR path: for local
    adapter: checkov_policy_index        # which adapter ingests it
    enabled: true
    license: "Apache-2.0"                # SPDX id, or "unknown"
    reuse_status: metadata_only          # see ReuseStatus below
    allowed_for_training: false          # governance-derived; see rules below
    notes: "Metadata only: IDs/resource-types/summaries. Never copy rule source."
```

A `SourceEntry` must set **exactly one** of `url` (an approved remote endpoint) or `path`
(a local file/dir, no network) — a model validator rejects entries that set both or
neither.

### `SourceType`

`scanner_rule_index` · `scanner_rule_catalog` · `provider_guidance` · `control_framework`
· `local_scenario_dir` · `local_rule_catalog` · `iac_repo`

### `ReuseStatus`

`full_reuse` · `attribution` · `metadata_only` · `mappings_only` · `restricted` ·
`unknown`

`mappings_only` was added under **FXL-D007**: it covers sources where our-id -> external
control-ID *mappings* are training-eligible, but the source's own control *text* is not.
See [Provenance and Licensing](Provenance-and-Licensing) for the full vocabulary and the
FXL-D007 decision.

## Governance rules (enforced by `registry.load_registry`)

`load_registry` parses the YAML, validates every entry with pydantic, and then applies
these rules as a normalization pass — so the **effective** `allowed_for_training` on every
entry is trustworthy regardless of what the YAML declared:

1. **`license: unknown` -> `allowed_for_training` forced `false`.** Unknown provenance is
   never training data, no matter what the file says.
2. **`reuse_status: restricted` -> `allowed_for_training` forced `false`.** The pattern may
   still live in the corpus for analysis; the training-export gate drops it.
3. **`reuse_status: metadata_only` -> `allowed_for_training` forced `false`.** The adapter
   must never copy rule source, rule logic, or benchmark control text into a `RiskPattern`
   — IDs, resource types, and short summaries only.
4. **`reuse_status: mappings_only` -> left as declared.** Per FXL-D007, our-id -> external
   control-ID mappings can be training-eligible even though the source's control text is
   not; the registry entry declares the intended value and the loader does not force it to
   `false`.
5. **Unsafe-operational content -> rejected at classification**, never enters the corpus at
   all (this is enforced downstream by the normalizer/validator, not the registry loader).

`full_reuse` and `attribution` entries keep their declared `allowed_for_training` flag
as-is. A malformed registry (missing `sources:` key, an entry that fails schema
validation) raises `RegistryError` — it fails loudly rather than silently dropping entries.

## The four source tiers

The registry organizes sources into four tiers by how directly they map to cloud-risk
patterns and how safe their reuse is:

| Tier | What | Reuse posture | Status in this epic |
|---|---|---|---|
| **1 — Scanner rule corpora** | Checkov / Trivy / Prowler policy indexes | `metadata_only` — IDs, resource types, titles, severities; **never** rule source/logic | Checkov is the one concrete, shipped adapter (`checkov_policy_index`), metadata-only, from a recorded fixture |
| **2 — Cloud-provider guidance** | AWS IAM Access Analyzer findings taxonomy, Well-Architected, Azure/GCP guidance | `attribution` — extract categories/summaries, attribute the source | Registry-scaffolded for the future; no adapter built in this epic |
| **3 — Control frameworks** | CSA CCM, CIS Benchmarks | CCM: `mappings_only` (FXL-D007); CIS: `metadata_only`, restricted pending human confirmation | Registry entries exist, disabled; no adapter ingests them yet |
| **4 — Public "bad-env" IaC** | Curated intentionally-vulnerable IaC repos | Local-curated-registry only, per-entry license, unknown -> not training-eligible | The seed rule catalog (`local-rule-catalog`) is this tier's dependable core (ticket #72) |

## The current `data/source_registry.yaml`

The file on `master` ships four entries today:

- **`checkov-terraform-index`** (Tier 1) — `enabled: true`, `metadata_only`,
  `allowed_for_training: false`. Ingested by `checkov_policy_index` from a recorded
  fixture in tests; the live URL is only touched by the registry-gated fetcher, never a
  crawler.
- **`local-rule-catalog`** (Tier 4) — `enabled: true`, `full_reuse`,
  `allowed_for_training: true`. Points at `data/rule_catalog/seed_patterns.yaml`, the
  hand-authored seed corpus (not yet authored — see ticket #72). Ingested by
  `rule_catalog_yaml`.
- **`local-scenarios-out`** — `enabled: false` until `out/` has generated scenarios to
  ingest. Ingested by `cloudforge_scenario`.
- **`csa-ccm`** and **`cis-benchmarks`** (Tier 3) — both `enabled: false`, registry-
  scaffolded for the future per FXL-D007; no adapter ingests either yet.

## Adding a source

1. Add an entry to `data/source_registry.yaml` with a stable `id`, the correct `type`,
   exactly one of `url`/`path`, the adapter that will ingest it, and an honest `license` /
   `reuse_status`. Default `allowed_for_training` conservatively — the governance rules
   above will force it to `false` for `unknown`/`restricted`/`metadata_only` regardless.
2. If the source needs a new extraction shape, add an adapter — see
   [Source Adapters](Source-Adapters).
3. Leave `enabled: false` until the adapter exists and is tested; the fetcher and ingester
   both skip disabled entries rather than erroring.
4. Never point `url` at anything that requires crawling, pagination-following, or
   site-wide search — one entry, one fixed URL or local path.

## Related pages

- [Learning Corpus](Learning-Corpus) — the pipeline this registry gates.
- [Provenance and Licensing](Provenance-and-Licensing) — how registry fields become
  per-pattern provenance, and the full reuse-status vocabulary.
- [Source Adapters](Source-Adapters) — the adapters that read registry-gated sources.
