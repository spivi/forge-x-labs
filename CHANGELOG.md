# Changelog

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
