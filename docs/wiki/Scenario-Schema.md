# Scenario Schema

The `scenario.yaml` file captures **user intent**. It is validated on load by
`app/cloudforge/models/scenario.py` (Pydantic v2, `extra="forbid"`).

## Example

```yaml
cloud: aws
scenario_type: ci_cd_iam_chain
environment: staging
difficulty: medium
company_profile:
  type: b2b_saas
  size: small
  app_name: analytics-exporter
requirements:
  critical_chains: 1
  medium_findings: 2
  false_positives: 1
constraints:
  no_real_secrets: true
  no_destructive_permissions: true
  max_resources: 40
  deployable: false
```

## Fields

| Field | Type | Notes |
|-------|------|-------|
| `cloud` | `"aws"` / `"azure"` / `"gcp"` / `"k8s"` / `"multi_cloud"` | AWS families emit Terraform. Azure, GCP, and K8s families are graph-only. |
| `scenario_type` | string | Dispatches to a generator (for example `ci_cd_iam_chain`) |
| `environment` | string | for example `staging` |
| `difficulty` | string | for example `medium` |
| `company_profile.type/size/app_name` | string | Narrative context |
| `requirements.critical_chains` | int | Expected critical risk paths |
| `requirements.medium_findings` | int | Expected medium findings |
| `requirements.false_positives` | int | Expected benign/near-miss findings |
| `constraints.no_real_secrets` | bool | Must be true |
| `constraints.no_destructive_permissions` | bool | Must be true |
| `constraints.max_resources` | int | Graph node budget |
| `constraints.deployable` | bool | **Must be `false`**. A validator rejects `true`. |

Unknown fields are rejected (`extra="forbid"`), so typos fail at load time.
