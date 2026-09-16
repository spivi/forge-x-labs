# Provenance and Licensing

Every `RiskPattern` carries exactly one `PatternProvenance`. A pattern with
incomplete or missing provenance fails corpus validation. The training-export
gate reads provenance to decide whether a pattern may leave as training data.

## `PatternProvenance` fields

| Field | Notes |
|---|---|
| `source_id` | registry id |
| `source_name` | human name |
| `source_type` | registry `type` |
| `source_url_or_path` | origin |
| `source_license` | SPDX id, or `"unknown"` |
| `reuse_status` | see [Source Registry](Source-Registry.md) |
| `allowed_for_training` | derived from reuse status |
| `extraction_method` | for example `fixture_html_metadata` |
| `fetched_at` / `extracted_at` | timestamps passed in explicitly, never `datetime.now()` at import |
| `content_hash` | of the raw cached bytes |
| `adapter_name` / `adapter_version` | which extractor produced the record |
| `normalizer_version` | pinned once normalization runs |
| `confidence` | adapter default, 0..1 |
| `notes` | free text |

`model_config = ConfigDict(extra="forbid")`. Malformed provenance fails to
construct rather than dropping fields.

## Reuse rules in short

- Copying scanner rule source is not allowed for `metadata_only` sources.
- CSA CCM: control-id **mappings** may be recorded. Control **body text** may not.
- CIS Benchmarks: section IDs and titles only.
