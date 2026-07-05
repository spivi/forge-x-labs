# Graph Model

`graph.json` is the **source of truth** for a scenario. It is a normalized directed graph
defined by `app/cloudforge/models/graph.py`.

## Node types

`Account`, `VPC`, `Subnet`, `SecurityGroup`, `IAMRole`, `IAMPolicy`, `CICDIdentity`,
`S3Bucket`, `Application`, `DataSet`, `LogTrail`.

## Edge types

`assumes`, `can_pass_role`, `attached_policy`, `can_read`, `can_write`, `belongs_to_app`,
`stores_sensitive_data`, `exposed_to_internet`, `logs_to`, `has_security_group`,
`deployed_by`.

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

`attributes` carries the Terraform-relevant payload (IAM actions, CIDRs, ARNs) so the
emitter and the risk engine read the same facts the graph declares.

## Edge shape

```json
{ "from": "role-deploy", "to": "role-runtime", "type": "can_pass_role", "security": { "risk": "critical" } }
```

The JSON key is `from` (a Python keyword); the model uses a `from_` field with a `from`
alias and serializes `by_alias=True`. An edge's stable id is `from->type->to` — that is
exactly what ground-truth paths reference.

## Invariants (enforced)

- **Referential integrity** — every edge endpoint must resolve to a node
  (`ScenarioGraph` model validator).
- **Ground-truth consistency** — every node/edge a ground-truth path names must exist
  (checked by the [risk engine](Validation-Pipeline)).
- **Resource budget** — `len(nodes) ≤ constraints.max_resources`.
- **Safety** — no `IAMPolicy` node may grant a forbidden destructive action; each
  intentionally-broad grant must be documented by an expected finding.

## The `ci_cd_iam_chain` graph

14 nodes / 11 edges. The absence of a `customer-exports → logs_to → trail-main` edge is
itself the `s3_logging_missing` finding — ground truth models both what *is* and what is
*missing*.
