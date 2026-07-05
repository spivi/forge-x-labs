# Source Adapters

Adapters are the layer between a registry-gated, already-fetched raw source and the
learning corpus: each one reads a local cache location (never the network — that's the
fetcher's job, see [Source Registry](Source-Registry)) and emits a list of
`RawPatternRecord`s with fully-stamped provenance. Adapters live in
`app/cloudforge/learn/adapters/`.

## The `PatternAdapter` protocol

`app/cloudforge/learn/adapters/base.py` defines a structural (`Protocol`,
`runtime_checkable`) interface — concrete adapters don't need to inherit from a base
class, they just need to match the shape:

```python
class PatternAdapter(Protocol):
    adapter_name: str
    adapter_version: str

    def extract(self, source: SourceEntry, raw_path: Path) -> list[RawPatternRecord]: ...
```

`raw_path` is always a local, already-fetched cache location. Implementations must respect
the source's `reuse_status` — most importantly, a `metadata_only` source must never copy
rule source text into a record, only IDs/resource-types/short summaries.

Every adapter stamps its own `adapter_name` and `adapter_version` into each record's
`provenance`, so a corpus record's origin — including exactly which version of the
extraction logic produced it — is always reproducible.

## The three shipped adapters

| # | Adapter | Module | Source | Confidence default | `training_eligible` default |
|---|---|---|---|---|---|
| 1 | `cloudforge_scenario` | `adapters/cloudforge_scenario.py` | existing `out/<scenario>` dirs | **0.85** | **true** |
| 2 | `rule_catalog_yaml` | `adapters/rule_catalog_yaml.py` | a local curated YAML rule catalog | **0.75** | **true** |
| 3 | `checkov_policy_index` | `adapters/checkov_policy_index.py` | recorded fixture HTML of the Checkov Terraform policy index | **0.55** | **false** (metadata-only) |

### `cloudforge_scenario`

Ingests existing `out/<scenario>` dirs produced by `cloudforge generate`:
`scenario.yaml` / `graph.json` / `expected_findings.json` / `ground_truth_paths.json`.
These are already validated and self-consistent (they went through the product's own
`generate → validate` pipeline), so this adapter reuses the existing product models and
loaders (`ScenarioSpec`, `ScenarioGraph`, `ExpectedFindings`, `GroundTruthPaths`) rather
than re-parsing JSON/YAML by hand.

One `RawPatternRecord` is emitted per scenario dir, keyed on its most severe ground-truth
path: title from `scenario_type` + path severity, summary from the path's explanation,
resource types from the nodes the path visits, remediation from findings that overlap the
path. Content hash is a stable SHA-256 over the sorted-key JSON of the graph, findings, and
ground-truth path together, so re-ingesting the same scenario dir is idempotent.

The registry entry for this adapter (`local-scenarios-out`) ships `enabled: false` until
`out/` has generated scenarios to ingest.

### `rule_catalog_yaml`

Parses a **local, curated** YAML rule catalog — a Tier-4 source per
[Source Registry](Source-Registry) — with a top-level `entries:` list, each a
hand-authored defensive cloud-risk pattern (`id`, `title`, `summary`, `cloud_provider`,
`domains`, `weakness_family`, `severity`, `affected_resource_types`, `remediation`,
`references`). One `RawPatternRecord` is emitted per entry.

This adapter is what will ingest the seed rule catalog
(`data/rule_catalog/seed_patterns.yaml`, >=12 hand-authored patterns spanning AWS/Azure/GCP
and multiple domains) once it is authored — see ticket #72, not yet done as of this
writing. The registry entry (`local-rule-catalog`) is `full_reuse` /
`allowed_for_training: true` since these patterns are wholly owned by this repo.

This adapter does **not** normalize into a `RiskPattern` and does not build graph
fragments — that is the (planned) normalizer's job (ticket #66).

### `checkov_policy_index`

**Metadata-only**, by design, regardless of what the registry entry declares. Extracts
policy IDs, resource types, titles, and severity from a **recorded fixture** HTML of the
Checkov Terraform policy index — never the live site (fetching is the registry-gated
fetcher's job) and never rule source or rule logic, only the same short metadata a human
browsing the public index page would see.

Parsing uses the stdlib `html.parser.HTMLParser` (no BeautifulSoup dependency): a small,
deliberately tolerant table-row collector that degrades to fewer/zero rows on malformed
markup rather than raising. A missing/unreadable fixture file *is* a hard error
(`CheckovParseError`), since that's an operator mistake rather than a page-shape
difference.

This adapter unconditionally sets `reuse_status = metadata_only` and
`allowed_for_training = False` on every record it emits — it does not trust the registry
entry's declared values for this, matching the Tier-1 governance posture even if a future
registry edit tried to relax it.

## Adding a new adapter

1. Add a module under `app/cloudforge/learn/adapters/` implementing `PatternAdapter`
   (`adapter_name`, `adapter_version`, `extract(source, raw_path) -> list[RawPatternRecord]`).
2. Stamp complete `PatternProvenance` on every record — `source_id`, `source_name`,
   `source_type`, `source_url_or_path`, `source_license`, `reuse_status`,
   `allowed_for_training`, `extraction_method`, `fetched_at`, `extracted_at`,
   `content_hash`, `adapter_name`, `adapter_version`, `normalizer_version` (leave as
   `"unset"`/`"unnormalized"` until the normalizer stamps its own), `confidence`.
3. Respect the source's `reuse_status` in what you extract — a `metadata_only` or
   `mappings_only` source must never have its full text copied into a record.
4. Add a registry entry in `data/source_registry.yaml` pointing at the new adapter (see
   [Source Registry](Source-Registry)) and unit tests driven entirely by fixtures — no
   internet, terraform, checkov, or OPA required for the default test run.

## Related pages

- [Source Registry](Source-Registry) — the allow-list adapters read from.
- [Risk Pattern Ontology](Risk-Pattern-Ontology) — the `RiskPattern` shape a `RawPatternRecord` eventually normalizes into.
- [Provenance and Licensing](Provenance-and-Licensing) — the provenance fields every adapter must stamp.
