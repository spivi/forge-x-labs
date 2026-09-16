<p align="center">
  <img src="docs/assets/logo.png" alt="Forge X Labs" width="360">
</p>

<h1 align="center">Forge X Labs — <code>cloudforge</code></h1>

<p align="center">
  Generate a unique, validated, <strong>never-applied</strong> AWS misconfig lab
  per student — no cloud account required.
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache_2.0-blue.svg" alt="License"></a>
  <img src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white" alt="Python 3.12">
  <img src="https://img.shields.io/badge/AWS-Never--Applied-FF9900?logo=amazon-aws&logoColor=white" alt="AWS Never-Applied">
  <img src="https://img.shields.io/badge/Cost-$0_Cloud_Spend-success" alt="$0 Cloud Spend">
</p>

<p align="center">
  <img src="docs/demo/cloudforge-vs-cloudgoat.gif" alt="Cloudforge vs CloudGoat Value Proposition Demo" width="760">
  <br>
  <em><a href="docs/demo/cloudforge-vs-cloudgoat.mp4">Watch high-resolution MP4 demo</a></em>
</p>

---

## Job

A trainer, SOC lead, or detection-eng onboarding owner needs analysts to
practice finding a **cloud-risk path** — and cannot hand everyone a sandbox
AWS account.

`cloudforge` generates a labeled estate (risk graph + Terraform + ground
truth), hides the answer key from the student, and auto-grades a guessed
path. This is a **tabletop / static-analysis lab**, not a deploy-to-AWS
range.

## vs CloudGoat / TerraGoat

| | CloudGoat | TerraGoat | cloudforge |
|---|---|---|---|
| Student gets | A live AWS account | A static `.tf` tree | A generated estate: brief + graph view + never-applied Terraform |
| AWS account | Required | No | **No** |
| Same lab for everyone | Yes | Yes | No — `--seed` / composer decoys |
| Auto-grade the path | No | No | `cloudforge grade` |
| You learn | Console muscle memory | Whether a scanner flags a resource | Attack **paths** and labeled false positives |

We lose on live console practice and catalog depth. We win on no account,
per-student copies, and a machine-checkable key.

## Install

Python **3.12+**. Contributors use Poetry; users can install the package:

```bash
pip install -e .
cloudforge version
```

Or with Poetry:

```bash
poetry env use 3.12
poetry install
PYTHONPATH=. poetry run python -m app.cli version
```

If `.venv/bin/cloudforge` has a stale shebang, use `python -m app.cli`.

Optional on `PATH` for `validate`: `terraform`, `checkov`, `opa`. Missing
tools are skipped (WARN), not a hard fail.

## 15 minutes

Generate, check, and read one lab (works on this tree):

```bash
cloudforge generate examples/ci_cd_iam_chain.yaml --out out/scenario_001 --engine composer --seed 17
cloudforge validate out/scenario_001
cloudforge report   out/scenario_001
```

Open `out/scenario_001/report.md`. The critical path is
`github-actions-oidc → DeployRole → RuntimeRole → customer-exports`. Checkov
typically catches the resource-level findings and **misses the PassRole
chain** — that miss is the teaching point.

### Trainer loop (`lab` / `grade` / `lab-cohort` / `grade-cohort`)

Generate per-student lab packs with separate student and instructor partitions:

```bash
# Generate a student lab pack (deterministic, zero cloud cost)
cloudforge lab examples/ci_cd_iam_chain.yaml --seed 17 --out out/alice
# student/    — brief.md, estate.html, estate.json, terraform/ (no answer key)
# instructor/ — report.md, expected_findings.json, grade_key.json

# Grade a student's attack path and misconfiguration guesses
cloudforge grade out/alice --submission alice_guess.yaml
# Reports attack path precision/recall, finding precision/recall, and composite score

# Batch generate unique labs for an entire class/cohort
cloudforge lab-cohort examples/ci_cd_iam_chain.yaml --students names.txt --out out/cohort
cloudforge grade-cohort out/cohort --submissions out/subs
```

The student pack strictly strips `expected_findings.json`, ground-truth attack paths,
and risk annotations (`security.risk` / `criticality`) per FXL-D010.

### Interactive Layered Architecture Workbench (`estate.html` & `cloudforge challenge`)

Generate a standalone interactive challenge HTML workbench or view it inside a student lab pack:

```bash
# Generate a standalone interactive challenge HTML workbench
cloudforge challenge examples/ci_cd_iam_chain.yaml --out challenge.html --seed 17

# Or find it inside any generated student pack:
# out/alice/student/estate.html
```

Every challenge workbench is 100% self-contained and offline-first (zero CDN or internet dependencies):
- **5-Tier Architecture Layout**: Organizes resources cleanly into Perimeter, Compute, Storage, Services, and Identity tiers with official AWS vector icons.
- **Mission Briefing Objective**: Displays scenario goals and context directly on the workbench.
- **Visual Attack-Path Builder**: Students click resource nodes sequentially to draft an attack trajectory with numbered step badges.
- **Misconfiguration Triage Checklist**: Filter and flag suspected vulnerable resources and finding categories.
- **One-Click YAML Export**: Generates conformant `submission.yaml` with copy-to-clipboard or direct file download.
- **Deterministic Live Evaluation**: Students can test their hypothesis against client-side grading logic before official submission.

## Scenario Families (12 Catalog Families in v1.0)

| `scenario_type` | Teaching Point / Learning Outcome | Example Config |
|---|---|---|
| `ci_cd_iam_chain` | CI OIDC identity → PassRole escalation → sensitive data exfil | `examples/ci_cd_iam_chain.yaml` |
| `public_data_exposure` | Public-read S3 bucket with PII + realistic decoy buckets | `examples/public_data_exposure.yaml` |
| `cross_account_trust` | External account (`999999999999`) trust relation into sensitive data | `examples/cross_account_trust.yaml` |
| `kms_key_overbroad` | Overbroad KMS key policy allowing wildcard `kms:Decrypt` | `examples/kms_key_overbroad.yaml` |
| `public_ebs_snapshot` | Unencrypted EBS volume snapshot shared publicly (`all`) | `examples/public_ebs_snapshot.yaml` |
| `iam_privesc_policy_version` | `iam:CreatePolicyVersion` bypass to `AdministratorAccess` | `examples/iam_privesc_policy_version.yaml` |
| `ec2_imds_credential_exfil` | SSRF / IMDSv1 hop allowing instance role credential exfiltration | `examples/ec2_imds_credential_exfil.yaml` |
| `lambda_public_function_url` | Unauthenticated Function URL (`NONE`) accessing private data | `examples/lambda_public_function_url.yaml` |
| `secretsmanager_policy_overbroad` | Resource policy granting wildcard `secretsmanager:GetSecretValue` | `examples/secretsmanager_policy_overbroad.yaml` |
| `public_rds_instance` | Internet-facing RDS instance with public ingress (`0.0.0.0/0`) | `examples/public_rds_instance.yaml` |
| `ecr_repository_public_read` | Public container registry policy leaking deployment credentials | `examples/ecr_repository_public_read.yaml` |
| `sqs_queue_overbroad_policy` | Overbroad SQS queue policy permitting message injection/theft | `examples/sqs_queue_overbroad_policy.yaml` |

AWS Terraform only. Dummy account `000000000000`. Never applied.

## Safety

- **Never** `terraform apply`. No AWS credentials. `deployable: true` is rejected.
- No real secrets. No offensive/operational content.
- Destructive IAM (`iam:Delete*`, `s3:DeleteBucket`, `ec2:TerminateInstances`,
  `kms:ScheduleKeyDeletion`, `organizations:*`) is a validation FAIL.
- Broad read/list grants are allowed only when documented as expected findings.
- **No ML / LLM / diffusion / GPU / Modal in v1.** Uniqueness is combinatoric
  (seed, decoys, path hops). A future generator would still have to pass these
  validators.

See [SECURITY.md](SECURITY.md) and [Safety & Scope](docs/wiki/Safety-and-Scope.md).

## `generate` / `validate` / `report`

```
out/scenario_001/
├── scenario.yaml              # intent
├── graph.json                 # SOURCE OF TRUTH
├── terraform/                 # compiled artifact, never applied
├── expected_findings.json
├── ground_truth_paths.json
└── report.md
```

`validate` is fail-soft: missing checkov/opa/terraform → WARN. A real schema
or risk-engine failure → FAIL and exit 1.

## Learning corpus

`cloudforge learn` is a **data** pipeline (fetch → ingest → validate → export),
not a training loop. Allow-list only (`data/source_registry.yaml`). It does
not train a model. See [Learning Corpus](docs/wiki/Learning-Corpus.md).

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md). Product code lives in `app/cloudforge/`.
Maintainer scaffolding (`.dev-context/`, `lemmings/`, `flavors/`) is not the
product.

```bash
ruff check --fix && ruff format
mypy --strict app/
PYTHONPATH=. .venv/bin/pytest tests/cloudforge tests/security -q --no-cov
```

## Docs

[`docs/wiki/`](docs/wiki/) — Architecture, Graph Model, Validation Pipeline,
Scenario Families, [Labs](docs/wiki/Labs.md), Safety. Diffusion pages are
**not in v1**.

License: [Apache-2.0](LICENSE).
