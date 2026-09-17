# Scenario Families

A **scenario family** is a named `scenario_type` with a registered builder
in the template generator and the composer.

## Shipped in v1.0 (AWS)

| `scenario_type` | Teaching point |
|---|---|
| `ci_cd_iam_chain` | GitHub Actions OIDC assumes DeployRole, which can PassRole a RuntimeRole that reads a sensitive bucket. |
| `public_data_exposure` | Public-read S3 bucket with PII and realistic decoy buckets. |
| `cross_account_trust` | Dummy account `999999999999` trusted into a role that can read sensitive data. |
| `kms_key_overbroad` | KMS key policy grants `kms:Decrypt` to `*`. |
| `public_ebs_snapshot` | Unencrypted snapshot with create-volume permission `group = all`. |
| `iam_privesc_policy_version` | `iam:CreatePolicyVersion` bypass to `AdministratorAccess`. |
| `ec2_imds_credential_exfil` | SSRF / IMDSv1 hop allowing instance-role credential exfil. |
| `lambda_public_function_url` | Unauthenticated Function URL (`NONE`) reaching private data. |
| `secretsmanager_policy_overbroad` | Resource policy grants wildcard `secretsmanager:GetSecretValue`. |
| `public_rds_instance` | Internet-facing RDS with `0.0.0.0/0` ingress. |
| `ecr_repository_public_read` | Public container registry leaking deploy tokens. |
| `sqs_queue_overbroad_policy` | Wildcard SQS policy. |

## Multi-cloud (v1.3)

| `scenario_type` | Teaching point |
|---|---|
| `k8s_pod_irsa_exfil` | Pod binds an IRSA token, federates to an IAM role, reads a sensitive bucket. |
| `azure_imds_keyvault_harvest` | App Service managed identity reads Key Vault. |
| `gcp_workload_identity_federation` | Workload Identity Pool federates to a service account that reads GCS. |

Examples live in `examples/<type>.yaml`.

The last three families emit matching Terraform (`k8s.tf`, `azure.tf`,
`gcp.tf`) plus any AWS resources on the path. Still never applied. AWS-only
labs do not pull those providers.

### Vendor pools (v1.4)

The composer pads every family from a pool of non-core fragments keyed by the
spec's `cloud` (`generate/composer_kinds.py`, `POOLS`). Each pool carries its
own noise, one decoy, one false positive and one compensating control, built
from node types the vendor's emitter and the workbench zones already cover:
`aws` is the original S3 / SQS / KMS / IAM / ECR / trail set, `azure` is
containers, key vaults, managed identities, app services and resource groups,
`gcp` is buckets, service accounts, projects, folders and workload identity
pools, and `k8s` is namespaces, pods, service accounts and a second cluster
on top of the whole AWS pool, because that family's path federates into AWS
IAM. `variation_axes` (`decoy` / `fp` / `ctrl`) and `difficulty` count
instances per role, whatever vendor kind fills the slot.

### `ci_cd_iam_chain` (detail)

**Critical path:** `github-actions-oidc -> DeployRole -> RuntimeRole ->
customer-exports -> customer-export-data`.

**Findings:** `iam_passrole_risk` (critical), `iam_excessive_privilege` (high),
`s3_logging_missing` (medium), `security_group_overexposed` (medium),
`public_looking_bucket_with_compensating_control` (benign false-positive).

## Adding a family

1. Author a core fragment under `generate/fragments/` and a template projection.
2. Register the builder in `template_generator.py` and the composer kind map.
3. Add `examples/<type>.yaml`.
4. Join the composer integrity net (seeds `{0,1,2,17,99}`, zero FAIL).

Keep every family **self-consistent**: the ground truth must reference only
nodes/edges present in the graph, and every broad grant must have a documenting
finding, or the risk engine will `FAIL`.
