# Changelog

## Unreleased

- Apache-2.0 license, SECURITY.md, CONTRIBUTING.md, and a job-first README.
- Variation harness (`cloudforge variation`) with a diversity gate (PRs #143, #146).
- Trainer loop: `cloudforge lab`, `grade`, `lab-cohort`, `grade-cohort` (PR #147).
- Scenario families: `cross_account_trust` (PR #149), `kms_key_overbroad` and
  `public_ebs_snapshot` (PR #151).

## 0.1.0

- Deterministic `generate` / `validate` / `report` for AWS misconfig scenarios.
- Families `ci_cd_iam_chain` and `public_data_exposure`.
- Graph composer, mutation engine, learning-corpus CLI (`cloudforge learn`).
- Fail-soft terraform / checkov / opa; never `terraform apply`.
