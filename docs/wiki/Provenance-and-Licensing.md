# Provenance and Licensing

## No provenance, no corpus

Every `RiskPattern` carries **exactly one** `PatternProvenance` (`pattern_models.py`) —
this is not optional. A pattern with incomplete or missing provenance fails corpus
validation (design intent for the corpus-validation gate, ticket #70). Provenance is where
governance actually lives: it is the field the training-export gate reads to decide whether
a pattern may ever leave the corpus as training data.

## `PatternProvenance` fields

| Field | Type | Notes |
|---|---|---|
| `source_id` | `str` | registry id (matches a `SourceEntry.id`) |
| `source_name` | `str` | human name |
| `source_type` | `SourceType` | the registry `type` |
| `source_url_or_path` | `str` | where it came from |
| `source_license` | `str` | SPDX id, or `"unknown"` |
| `reuse_status` | `ReuseStatus` | see vocabulary below |
| `allowed_for_training` | `bool` | governance-derived (see [Source Registry](Source-Registry)) |
| `extraction_method` | `str` | e.g. `fixture_html_metadata`, `scenario_dir`, `yaml_parse` |
| `fetched_at` | `datetime` | when the raw cache was written |
| `extracted_at` | `datetime` | when the adapter ran |
| `content_hash` | `str` | of the raw cached bytes |
| `adapter_name` | `str` | which adapter produced this record |
| `adapter_version` | `str` | pinned, for reproducibility |
| `normalizer_version` | `str` | pinned once normalization runs (ticket #66) |
| `confidence` | `float` (0..1) | the adapter's default, carried through |
| `notes` | `str` | free text, e.g. "metadata only; rule source not copied" |

`model_config = ConfigDict(extra="forbid")` — same convention as every other model in the
product; an incomplete or malformed provenance payload fails to construct rather than
silently dropping fields. Timestamps are always passed in explicitly (never
`datetime.now()` at import/default time), consistent with the rest of the codebase's
determinism discipline.

## The `reuse_status` vocabulary

Defined in `app/cloudforge/learn/source_models.py` (`ReuseStatus`):

| Value | Meaning | Training-eligible? |
|---|---|---|
| `full_reuse` | Fully owned or permissively licensed; free reuse | Yes, if otherwise valid/safe |
| `attribution` | Reusable if the source is attributed (name + URL, always carried in provenance) | Yes, if otherwise valid/safe |
| `metadata_only` | Extract IDs / resource-types / short summaries ONLY — never rule source, rule logic, or benchmark control text | **No** — forced `allowed_for_training: false` |
| `mappings_only` | Our-id -> external control-ID **mappings** are reusable; the source's own control **text** is not | **Yes for the mapping itself** — left as declared by the registry (FXL-D007) |
| `restricted` | Reuse rights unconfirmed or explicitly limited | **No** — forced `allowed_for_training: false`; excluded from training export |
| `unknown` | License/reuse posture not established | **No** — forced `allowed_for_training: false` |

`NON_TRAINING_REUSE` (`source_models.py`) is the frozenset `{restricted, metadata_only,
unknown}` — these three are always excluded from `training_eligible`, regardless of what a
registry entry's `allowed_for_training` flag says. `mappings_only` is deliberately **not**
in that set.

## Governance is enforced, not just documented

The registry loader (`learn/registry.py`, `load_registry`) applies these rules as a
normalization pass on every load:

1. `license: unknown` -> `allowed_for_training` forced `false`.
2. `reuse_status: restricted` -> `allowed_for_training` forced `false`.
3. `reuse_status: metadata_only` -> `allowed_for_training` forced `false`.
4. `reuse_status: mappings_only` -> left **as declared** in the registry file (this is the
   one status the loader does not force to `false`).

`RiskPattern.training_eligible` (a computed field, not settable) then re-checks
`provenance.reuse_status not in NON_TRAINING_REUSE` at the pattern level, so the exclusion
is enforced twice — once when the registry is loaded, and again on every individual
pattern — rather than relying on a single check somewhere in the pipeline.

## FXL-D007 — CSA CCM mappings are training-eligible; control text is not; CIS stays restricted

**Decision (accepted, 2026-07-05):** The learning corpus can map cloudforge weakness
families to external control frameworks. CSA publishes the Cloud Controls Matrix (CCM)
machine-readably (JSON/YAML/OSCAL); CIS Benchmark content is more restricted.

- **CSA CCM:** our-id -> CCM control-ID **mappings** are training-eligible
  (`reuse_status: mappings_only`, `allowed_for_training: true`). The corpus may record
  which CCM control a pattern maps to (`control_mappings`). Copying CCM control **body
  text** into the corpus or the training export is **not** permitted.
- **CIS Benchmarks:** stay `metadata_only` / not-training-eligible — section IDs and
  titles only, never the benchmark text — until reuse rights are separately confirmed.

**Consequence:** any adapter that touches CSA CCM must emit `control_mappings` (ID
references) only, never control body text; a corpus-validation check must reject any
CCM-sourced record carrying control body text. No CCM/CIS adapter is built in this epic —
both registry entries (`csa-ccm`, `cis-benchmarks`) ship `enabled: false`, scaffolded for
the future. Revisit CIS if reuse rights are later confirmed. (Full text: `DECISIONS.md`,
FXL-D007.)

This is why `mappings_only` exists as its own `reuse_status` distinct from
`metadata_only` — the two encode genuinely different governance postures (mapping IDs vs.
copying text) that would otherwise be conflated.

## Human-call sources stay conservative until confirmed

Both CSA CCM and CIS Benchmarks reuse rights required — and got, via FXL-D007 — an
explicit human decision rather than a default assumption. Until a human confirms broader
reuse, both stay on the restrictive side of their respective vocabularies. This pattern —
default to the more conservative `reuse_status`, escalate to a recorded `FXL-D` decision
before relaxing it — is the model for any future source whose license terms are unclear.

## Related pages

- [Source Registry](Source-Registry) — where these fields originate, and the full
  governance-rule enforcement at load time.
- [Risk Pattern Ontology](Risk-Pattern-Ontology) — how `training_eligible` is derived from
  provenance on the pattern itself.
- [Corpus Quality Scoring](Corpus-Quality-Scoring) — provenance completeness as a quality
  dimension.
