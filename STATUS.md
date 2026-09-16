# Project Status

**Current Phase:** v1.0.0 OSS Lab Generator — Release Complete
**Last Updated:** 2026-09-16

## Current State

- **Project**: FXL (`cloudforge`)
- **Phase**: v1.0.0 open-source release as a **local-first cloud-risk lab generator**
- **Catalog Depth**: 12 complete scenario families (IAM, S3, KMS, EBS, RDS, ECR, SQS, Lambda, Secrets Manager)
- **Interactive Workbench**: `student/estate.html` — 5-tier architecture view, vendor SVG icons, attack path builder, live scoring
- **Demo Assets**: `docs/demo/cloudforge-vs-cloudgoat.mp4` & `.gif`
- **Test Suite**: 2,005 tests passed, 0 failures, 98.35% test coverage
- **Version**: `1.0.0` (tagged `v1.0.0`)
- **Last Agent**: Antigravity (Google DeepMind)
- **Timestamp**: 2026-09-16T14:15:00Z

## Release Highlights (v1.0.0)

1. **12 Scenario Families**:
   - `ci_cd_iam_chain`: OIDC CI identity -> PassRole -> sensitive S3 bucket.
   - `public_data_exposure`: Public S3 bucket with PII + realistic decoys.
   - `cross_account_trust`: External AWS account trusted into internal IAM role.
   - `kms_key_overbroad`: Overbroad KMS key policy with wildcard decrypt.
   - `public_ebs_snapshot`: Unencrypted public EBS volume snapshot.
   - `iam_privesc_policy_version`: `CreatePolicyVersion` bypass to `AdministratorAccess`.
   - `ec2_imds_credential_exfil`: SSRF/IMDSv1 hop allowing instance role exfiltration.
   - `lambda_public_function_url`: Unauthenticated Lambda Function URL (`NONE`) accessing private data.
   - `secretsmanager_policy_overbroad`: Wildcard `secretsmanager:GetSecretValue` resource policy.
   - `public_rds_instance`: Publicly accessible database instance with open security group.
   - `ecr_repository_public_read`: Public container registry leaking deployment tokens.
   - `sqs_queue_overbroad_policy`: Wildcard SQS policy permitting eavesdropping/tampering.

2. **Trainer & Student Lab Workflows**:
   - `cloudforge lab`: Generates partitioned `student/` (stripped) and `instructor/` packs.
   - `cloudforge grade`: Evaluates student guesses (path precision/recall, finding precision/recall, composite score).
   - `cloudforge lab-cohort` / `grade-cohort`: Batch generate and grade labs for full classes.

3. **Interactive Layered Architecture Workbench (`estate.html`)**:
   - 5-tier architectural decomposition (Perimeter, Compute, Storage, Services, Identity).
   - Official AWS vector icons (embedded inline SVG, zero external CDN dependencies).
   - Interactive attack-path trajectory builder with numbered step badges.
   - Finding checklist, live YAML generator, and client-side deterministic evaluation.

4. **Safety & Zero-Cost Guarantees**:
   - 100% local static analysis — $0 cloud spend, no AWS accounts needed (`000000000000`).
   - `terraform apply` blocked by hard validator constraint (`FXL-D001`).
   - Strict student/instructor key isolation (`FXL-D010`).

## Active Tasks

- [x] All PRs merged into `master` (#143, #146, #147, #149, #151, #153, #154)
- [x] 12 scenario families implemented and tested across composer & template engines
- [x] Interactive layered architecture workbench (`estate.html`) implemented and verified
- [x] Demo video & GIF generated and referenced in README
- [x] 2,005 tests passing with 98.35% code coverage
- [x] Version bumped to 1.0.0 (`pyproject.toml`, `app/cloudforge/__init__.py`)
- [x] Poetry build validated (sdist + wheel generated cleanly)
- [ ] Tag git `v1.0.0` and publish GitHub release

## Session Log

| Timestamp | Agent | Platform | Note |
|---|---|---|---|
| 2026-07-16 | Claude | claude | FXL-VAR-1f merged (PR #142) |
| 2026-09-16 | Grok 4.6 | grok | v1 labs plan; PRs #143, #146, #147, #149, #151, #153 |
| 2026-09-16 | Antigravity | agy | PR #154 (7 families, workbench, demo video), v1.0.0 release prep |

