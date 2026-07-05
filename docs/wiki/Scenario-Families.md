# Scenario Families

A **scenario family** is a named `scenario_type` with a registered builder in
`app/cloudforge/generate/template_generator.py`.

## Shipped

### `ci_cd_iam_chain`

A staging b2b_saas environment. A GitHub Actions OIDC identity assumes a DeployRole; the
DeployRole can `iam:PassRole` a RuntimeRole; the RuntimeRole holds broad `s3:Get*/List*`
over a sensitive customer-exports bucket.

**Critical path:** `github-actions-oidc → DeployRole → RuntimeRole → customer-exports →
customer-export-data`.

**Findings:** `iam_passrole_risk` (critical), `iam_excessive_privilege` (high),
`s3_logging_missing` (medium), `security_group_overexposed` (medium),
`public_looking_bucket_with_compensating_control` (benign false-positive).

## Adding a family

1. Author node/edge/finding/path data (see `generate/ci_cd_iam_chain.py` as the model).
2. Register a builder in `_BUILDERS` keyed by the new `scenario_type`.
3. Add an example `examples/<type>.yaml`.
4. The pipeline, validators, and report need **no changes** — they read the graph.

Keep every family **self-consistent**: the ground truth must reference only nodes/edges
present in the graph, and every broad grant must have a documenting finding, or the risk
engine will `FAIL`.

## Planned families (not yet built)

Cross-account trust chains, over-permissive KMS key policies, public RDS/EBS snapshots,
missing-logging estates. Tracked in the [Roadmap](Roadmap).
