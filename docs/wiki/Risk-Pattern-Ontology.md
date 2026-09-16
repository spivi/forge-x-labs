# Risk Pattern Ontology

A `RiskPattern` is the normalized unit of the learning corpus. Defined in
`app/cloudforge/learn/pattern_models.py`, enums in `pattern_enums.py`.

`RiskPattern.graph_fragment` is a real `ScenarioGraph` (see
[Graph Model](Graph-Model.md)). `expected_findings` reuses
`ExpectedFinding` from `app.cloudforge.models.findings`. A pattern fragment
can be checked by the same validators a generated scenario uses.

## Fields

| Field | Notes |
|---|---|
| `id` | stable slug, for example `s3-public-read-aws-001` |
| `title` / `summary` | human text |
| `cloud_provider` / `domains` / `weakness_family` | enums |
| `severity` | `low` / `medium` / `high` / `critical` |
| `affected_resource_types` | for example `["aws_s3_bucket"]` |
| `risky_relationships` | edge-type semantics, for example `["can_pass_role"]` |
| `missing_controls` / `negative_controls` / `compensating_controls` | control lists |
| `graph_fragment` | `ScenarioGraph` |
| `expected_findings` | labeled findings |
| `remediation` / `detection_hints` | text |
| `control_mappings` | our IDs to external control IDs |
| `source_mappings` | external rule IDs (for example Checkov `CKV_AWS_20`) |
| `provenance` | required. No provenance, no corpus. |
