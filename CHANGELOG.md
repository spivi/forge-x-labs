# Changelog

## 1.3.1 (2026-09-17)

- The student workbench and the demo challenge page show the release version
  again (they still said 1.0.0).
- README: the workbench has seven zones, not five, and its finding checklist
  is the whole catalog rather than a per-vendor list. Two claim badges dropped.

## 1.3.0 (2026-09-17)

SOC roundtable pack and multi-cloud labs.

- `cloudforge roundtable`: unique student copies of the same identity-federation
  lesson across Kubernetes (IRSA), Azure (managed identity), and GCP (Workload
  Identity Pool). Writes `facilitator.md` with a 90-minute agenda.
- Those three families emit never-applied Terraform (`k8s.tf`, `azure.tf`,
  `gcp.tf`). AWS-only labs do not pull those providers.

## 1.1.0 (2026-09-17)

Three graph-only labs outside AWS Terraform:

- `k8s_pod_irsa_exfil`: pod IRSA token to an IAM role that reads a sensitive bucket.
- `azure_imds_keyvault_harvest`: App Service managed identity to Key Vault.
- `gcp_workload_identity_federation`: Workload Identity Pool to a GCS bucket.

These families generate a risk graph, workbench, and grade key. Terraform remains
AWS-only. Azure, GCP, and Kubernetes nodes do not emit `.tf` resources yet.

## 1.0.0 (2026-09-16)

Local-first AWS misconfig lab generator.

- 12 scenario families (IAM, S3, KMS, EBS, RDS, ECR, SQS, Lambda, Secrets Manager).
- `generate` / `validate` / `report` pipeline. Graph is source of truth; Terraform is compiled and never applied.
- Trainer loop: `lab`, `grade`, `lab-cohort`, `grade-cohort`, `challenge`.
- Interactive single-file workbench (`estate.html`).
- Variation harness (`cloudforge variation`) with a diversity gate.
- Learning corpus CLI (`cloudforge learn`): fetch, ingest, validate, export. No model training.
- Apache-2.0 license, SECURITY.md, CONTRIBUTING.md.

## 0.1.0

- Deterministic `generate` / `validate` / `report` for AWS misconfig scenarios.
- Families `ci_cd_iam_chain` and `public_data_exposure`.
- Graph composer, mutation engine.
- Fail-soft terraform / checkov / opa. Never `terraform apply`.
