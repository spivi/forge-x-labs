# Scenario Families

A **scenario family** is a named `scenario_type` with a registered builder
in the template generator and the composer.

Every path declares what the attacker reaches (`sink_kind` and `target` on
the ground-truth path and in the grade key). The "reaches" column is that
kind: `data` is a labeled data set; the others are the resource or identity
the path ends on.

## Shipped in v1.0 (AWS)

| `scenario_type` | Teaching point | Reaches |
|---|---|---|
| `ci_cd_iam_chain` | GitHub Actions OIDC assumes DeployRole, which can PassRole a RuntimeRole that reads a sensitive bucket. | data |
| `public_data_exposure` | Public-read S3 bucket with PII and realistic decoy buckets. | data |
| `cross_account_trust` | Dummy account `999999999999` trusted into a role inside the account; the partner data that role can read is a second path. | role |
| `kms_key_overbroad` | KMS key policy grants `kms:Decrypt` to `*`; the reader walks bucket -> key and holds the decrypt capability. | key |
| `public_ebs_snapshot` | Unencrypted snapshot with create-volume permission `group = all`. | snapshot |
| `iam_privesc_policy_version` | `iam:CreatePolicyVersion` on the policy of a role the developer can assume makes that role admin-capable; the payroll data it reads is a second path. | role |
| `ec2_imds_credential_exfil` | SSRF / IMDSv1 hop allowing instance-role credential exfil. | data |
| `lambda_public_function_url` | Unauthenticated Function URL (`NONE`) reaching private data. | data |
| `secretsmanager_policy_overbroad` | Resource policy grants an external account `secretsmanager:GetSecretValue` on the master credentials. | secret |
| `public_rds_instance` | Internet-facing RDS with `0.0.0.0/0` ingress. | database |
| `ecr_repository_public_read` | Public container registry: the image and what it embeds. | image |
| `sqs_queue_overbroad_policy` | Wildcard SQS policy: the messages in flight. | queue |

## Multi-cloud (v1.3)

| `scenario_type` | Teaching point | Reaches |
|---|---|---|
| `k8s_pod_irsa_exfil` | Pod binds an IRSA token, federates to an IAM role, reads a sensitive bucket. | data |
| `azure_imds_keyvault_harvest` | App Service managed identity reads Key Vault, whose stored key opens the customer container. The vault is the hop, not the ending: the lesson is that an IMDS token walks all the way to customer data. | data |
| `gcp_workload_identity_federation` | Workload Identity Pool federates to a service account that reads GCS. | data |

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

Every pool also mints data sets, so the sink is never the only `DataSet` on
the board: noise data sets are held by a container, bucket or pod and carry a
classification drawn from `public` / `internal` / `confidential` /
`restricted`; every compensating control guards a `restricted` data set that
no identity can reach; every core data set carries its true `restricted` label.

Nothing a path node carries is rare among its peers: pool nodes draw `env`
with `prod` as the common value and the core's owner and app weighted in, the
composer plans at least two off-path nodes of every path node type the pool
can mint, and after assembly it copies each path node's tag values and benign
attributes onto seeded off-path peers (`generate/composer_blend.py`). The
modeled-risk attributes and per-resource identifiers are the only values that
may exist on a path node alone; `tests/cloudforge/lab/test_path_tells.py`
prints that allowlist and holds every example to the rule.

### Path shape (v1.4)

The composer draws each estate's path shape from the difficulty band
(`generate/composer.py`, `_SHAPE_BANDS`) and hands it to the core fragment
as `extra_hops`, `prefix_hops`, `dead_end` and `lookalike`
(`generate/fragments/_core.py`). Identity-chain families insert the hops
between the entry's first identity and the resource with the vendor's own
edge (`can_pass_role`, `assumes`, `impersonates`); resource-shaped families
add an identity route (`generate/fragments/_aws_shape.py`) as a second
labeled path, a dead end from the entry and, on hard, a blocked lookalike of
the exposed resource. A fragment builds the same node types for the same
shape whatever the rng; the rng only picks names from `_vocab`.

### `ci_cd_iam_chain` (detail)

**Critical path (easy):** `github-actions-oidc -> DeployRole -> RuntimeRole ->
customer-exports -> customer-export-data`; medium and hard insert drawn
intermediate roles between DeployRole and RuntimeRole.

**Findings:** `iam_passrole_risk` (critical), `iam_excessive_privilege` (high),
`s3_logging_missing` (medium), `security_group_overexposed` (medium),
`public_looking_bucket_with_compensating_control` (benign false-positive).

## Adding a family

1. Author a core fragment under `generate/fragments/` and a template projection.
   Its path declares `sink_kind` and `target` (the last node); the composer
   refuses a path whose target is not the last node or has another type.
2. Register the builder in `template_generator.py` and the composer kind map.
3. Add `examples/<type>.yaml`.
4. Join the composer integrity net (seeds `{0,1,2,17,99}`, zero FAIL).

Keep every family **self-consistent**: the ground truth must reference only
nodes/edges present in the graph, and every broad grant must have a documenting
finding, or the risk engine will `FAIL`.
