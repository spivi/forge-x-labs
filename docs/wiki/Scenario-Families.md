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

### `public_data_exposure`

A prod data-lake estate. A public-read S3 bucket holds customer PII with no
compensating control. Distinct from the IAM *chain*: the data is one bucket
policy away from the internet.

## Landing in v1 (open PRs)

- `cross_account_trust` — PR #149. Dummy account `999999999999` trusted into a
  role that can read sensitive data.
- `kms_key_overbroad` — PR #151. KMS key policy grants `kms:Decrypt` to `*`.
- `public_ebs_snapshot` — PR #151. Unencrypted snapshot with create-volume
  permission `group = all`.

## Adding a family

1. Author a core fragment under `generate/fragments/` and a template projection.
2. Register the builder in `template_generator.py` and `composer.py` `_CORE_KINDS`.
3. Add `examples/<type>.yaml`.
4. Join the composer integrity net (seeds `{0,1,2,17,99}`, zero FAIL).

Keep every family **self-consistent**: the ground truth must reference only nodes/edges
present in the graph, and every broad grant must have a documenting finding, or the risk
engine will `FAIL`.
