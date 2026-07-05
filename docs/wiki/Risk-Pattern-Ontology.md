# Risk Pattern Ontology

A `RiskPattern` is the normalized unit of the learning corpus — the output of the
normalizer stage (design-intent; ticket #66) and, ultimately, of the training export. It is
defined in `app/cloudforge/learn/pattern_models.py`, with its classification/vocabulary
enums split out into `app/cloudforge/learn/pattern_enums.py` (both modules re-export each
other's names, so callers may import from either).

## Compatible with the existing graph model

`RiskPattern.graph_fragment` is a real `ScenarioGraph` — the exact same model used by the
scenario generator (see [Graph Model](Graph-Model)), built from the existing `NodeType` /
`EdgeType` / `GraphNode` / `GraphEdge` types. `expected_findings` reuses the existing
`ExpectedFinding` / `Severity` types from `app.cloudforge.models.findings`. This is
deliberate: a pattern's fragment is already in the product's own graph vocabulary, so it
can be validated by the same machinery a generated scenario is validated by.

## Fields

| Field | Type | Notes |
|---|---|---|
| `id` | `str` | stable slug, e.g. `s3-public-read-aws-001` |
| `title` | `str` | short human title |
| `summary` | `str` | 1-3 sentence description of the risk |
| `cloud_provider` | `CloudProvider` | see enums below |
| `domains` | `list[Domain]` | see enums below |
| `weakness_family` | `WeaknessFamily` | see enums below |
| `severity` | `Severity` | reuses the existing `low`/`medium`/`high`/`critical` type |
| `affected_resource_types` | `list[str]` | e.g. `["aws_s3_bucket"]` |
| `risky_relationships` | `list[str]` | edge-type semantics, e.g. `["can_pass_role"]` |
| `missing_controls` | `list[str]` | controls that should exist but don't |
| `negative_controls` | `list[str]` | controls actively misconfigured (e.g. public ACL) |
| `compensating_controls` | `list[str]` | controls that reduce the risk (benign-FP signal) |
| `graph_fragment` | `ScenarioGraph` | reuses the existing graph model — nodes + edges |
| `expected_findings` | `list[ExpectedFinding]` | reuses the existing findings model |
| `remediation` | `str` | how to fix |
| `detection_hints` | `list[str]` | what a scanner would look for |
| `control_mappings` | `list[str]` | our IDs -> external control IDs (CCM/CIS/etc.) |
| `source_mappings` | `list[str]` | external rule IDs (e.g. Checkov `CKV_AWS_20`) |
| `provenance` | `PatternProvenance` | **required — no provenance, no corpus** |
| `confidence` | `float` (0..1) | adapter-defaulted; see [Source Adapters](Source-Adapters) |
| `realism_score` | `float` (0..1) | scored by the (planned) quality module, ticket #69 |
| `quality_score` | `float` (0..1) | scored by the (planned) quality module, ticket #69 |
| `validation_status` | `ValidationStatus` | `unvalidated` / `valid` / `invalid` |
| `safety_classification` | `SafetyClassification` | see enums below |
| `training_eligible` | `bool` (computed) | **derived**, not free-form — see below |

`model_config = ConfigDict(extra="forbid")` — a `RiskPattern` rejects unknown fields, same
convention as every other Pydantic model in the product.

## Enums

### `CloudProvider`

`aws` · `azure` · `gcp` · `kubernetes` · `multi_cloud` · `generic`

### `Domain` (multi-valued via `domains: list[Domain]`)

`iam` · `storage` · `network` · `logging` · `encryption` · `ci_cd` · `secrets` · `data` ·
`compute` · `database` · `serverless` · `containers` · `monitoring` · `governance`

### `WeaknessFamily`

The first six values are kept **identical** to `models.findings.FindingFamily` so a
pattern's weakness family and a scenario's finding family share one vocabulary:

`iam_excessive_privilege` · `iam_passrole_risk` · `s3_logging_missing` ·
`s3_public_exposure` · `security_group_overexposed` ·
`public_looking_bucket_with_compensating_control`

Plus a generic, provider-agnostic list for patterns that don't map to an existing
cloudforge family:

`public_exposure` · `excessive_privilege` · `missing_encryption` · `missing_logging` ·
`weak_network_boundary` · `insecure_defaults` · `secrets_exposure` ·
`unrestricted_access` · `misconfigured_control` · `other`

### `SafetyClassification`

`defensive_pattern` · `benchmark_pattern` · `training_pattern` · `restricted_source` ·
`unsafe_operational` · `unknown`

The **trainable** subset (`TRAINABLE_CLASSIFICATIONS`) is `{defensive_pattern,
benchmark_pattern, training_pattern}`. `unsafe_operational` patterns must never reach the
corpus at all — the (planned) normalizer rejects them at classification time (ticket #66).

### `ValidationStatus`

`unvalidated` · `valid` · `invalid` — every pattern starts `unvalidated`; only the (planned)
fragment validator (ticket #67) promotes it to `valid`.

## `training_eligible` is derived, not free-form

`training_eligible` is a Pydantic `computed_field` — it cannot be set directly. Per the
design (honoring **FXL-D007**), a pattern is eligible iff:

```
validation_status == valid
AND safety_classification in {defensive_pattern, benchmark_pattern, training_pattern}
AND provenance.allowed_for_training == true
AND provenance.reuse_status not in {restricted, metadata_only, unknown}
```

Note that `mappings_only` is **not** in the excluded set — per FXL-D007, CCM control-ID
mappings can be training-eligible even though `metadata_only`, `restricted`, and `unknown`
never are. See [Provenance and Licensing](Provenance-and-Licensing) for the full reuse
vocabulary and the decision rationale.

## `PatternProvenance` and `RawPatternRecord`

Every `RiskPattern` carries exactly one `PatternProvenance` — see
[Provenance and Licensing](Provenance-and-Licensing) for its fields and the "no provenance,
no corpus" rule.

`RawPatternRecord` is the adapter's output shape, one step before normalization: a looser,
adapter-specific record (`title`, `summary`, `resource_types`, `rule_id`, `raw_payload`,
etc.) that still carries a complete `provenance`. The (planned) normalizer turns each
`RawPatternRecord` into a `RiskPattern` by mapping fields onto this ontology, building/
verifying the `graph_fragment`, and assigning `safety_classification` (ticket #66). See
[Source Adapters](Source-Adapters) for what each adapter currently emits.

## Related pages

- [Learning Corpus](Learning-Corpus) — where normalization sits in the overall pipeline.
- [Source Adapters](Source-Adapters) — what feeds `RawPatternRecord`s into normalization.
- [Provenance and Licensing](Provenance-and-Licensing) — the provenance model in full.
- [Corpus Quality Scoring](Corpus-Quality-Scoring) — how `quality_score`/`realism_score`
  are intended to be computed.
- [Graph Model](Graph-Model) — the `ScenarioGraph` that `graph_fragment` reuses.
