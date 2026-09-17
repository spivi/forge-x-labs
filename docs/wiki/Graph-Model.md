# Graph Model

`graph.json` is the **source of truth** for a scenario. It is a directed graph
defined by `app/cloudforge/models/graph.py`.

## Node types (v1)

AWS: `Account`, `VPC`, `Subnet`, `SecurityGroup`, `IAMRole`, `IAMPolicy`,
`CICDIdentity`, `S3Bucket`, `KmsKey`, `EbsSnapshot`, `EC2Instance`,
`LambdaFunction`, `SecretsManagerSecret`, `RdsInstance`, `EcrRepository`,
`SqsQueue`, `Application`, `DataSet`, `LogTrail`.

Kubernetes: `K8sCluster`, `K8sNamespace`, `K8sPod`, `K8sServiceAccount`,
`K8sRole`, `K8sRoleBinding`, `K8sSecret`.

Azure: `AzureManagementGroup`, `AzureSubscription`, `AzureEntraTenant`,
`AzureResourceGroup`, `AzureAppService`, `AzureManagedIdentity`,
`AzureRoleAssignment`, `AzureKeyVault`, `AzureStorageContainer`.

GCP: `GcpOrganization`, `GcpFolder`, `GcpProject`, `GcpComputeInstance`,
`GcpServiceAccount`, `GcpWorkloadIdentityPool`, `GcpStorageBucket`.

Azure, GCP, and Kubernetes nodes are modeled in the graph and emit never-applied
Terraform (`azure.tf`, `gcp.tf`, `k8s.tf`). Org, subscription, and cluster
nodes stay passive (no resource block).

## Edge types (v1)

`assumes`, `can_pass_role`, `attached_policy`, `can_read`, `can_write`,
`belongs_to_app`, `stores_sensitive_data`, `exposed_to_internet`, `logs_to`,
`has_security_group`, `deployed_by`, `can_decrypt`, `can_invoke`,
`organizational_child`, `applies_scp`, `in_namespace`,
`binds_service_account`, `federates_to`, `impersonates`, `role_assigned_to`.

## Node shape

```json
{
  "id": "role-runtime",
  "type": "IAMRole",
  "name": "RuntimeRole",
  "tags": { "env": "staging", "owner": "platform-team", "app": "analytics-exporter" },
  "security": { "criticality": "critical" },
  "attributes": { "actions": ["s3:Get*", "s3:List*"], "resource": "arn:aws:s3:::customer-exports/*" }
}
```

`attributes` carries the Terraform-relevant payload (IAM actions, CIDRs, ARNs)
so the emitter and the risk engine read the same facts.

## Edge shape

```json
{ "from": "role-deploy", "to": "role-runtime", "type": "can_pass_role", "security": { "risk": "critical" } }
```

The JSON key is `from` (a Python keyword). The model uses a `from_` field with
a `from` alias. An edge's stable id is `from->type->to`. Ground-truth paths
use that id.

## Invariants (enforced)

- **Referential integrity**: every edge endpoint must resolve to a node.
- **Ground-truth consistency**: every node/edge a ground-truth path names
  must exist (checked by the [risk engine](Validation-Pipeline.md)).
- **Resource budget**: `len(nodes) <= constraints.max_resources`.
- **Safety**: no `IAMPolicy` node may grant a forbidden destructive action.
  Each intentionally-broad grant must be documented by an expected finding.
