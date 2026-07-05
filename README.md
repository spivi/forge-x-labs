<p align="center">
  <img src="docs/assets/logo.png" alt="Forge X Labs" width="360">
</p>

<h1 align="center">Forge X Labs — <code>cloudforge</code></h1>

<p align="center">
  Local-first generation of <strong>validated</strong> cloud-risk scenarios for scanner
  benchmarking, security training, and prioritization research.
</p>

---

## What it is

`cloudforge` is a **local-first cloud-misconfiguration scenario generator**. It produces
realistic, **labeled, validated** cloud-risk scenarios as:

- a normalized **risk graph** (`graph.json`) — the source of truth,
- **never-applied Terraform** (`terraform/`) — a compiled artifact for static scanning,
- **ground truth**: intended risk paths + expected findings (`ground_truth_paths.json`,
  `expected_findings.json`),
- a human-readable **report** (`report.md`).

The core thesis: cloud-misconfiguration scenario generation is not about generating
vulnerable Terraform — it is about generating **realistic, labeled, validated cloud-risk
graphs** with machine-checkable ground truth.

Use cases: scanner benchmarking, cloud-security training, prioritization-engine
evaluation, remediation-order testing, analyst exercises, and (future) generative-graph
research.

## What it is NOT

- ❌ Not a deployer. It **never** runs `terraform apply` and needs **no AWS credentials**.
- ❌ Not an exploit toolkit. No offensive/operational content — **defensive research only**.
- ❌ Not (yet) an LLM/diffusion system. MVP generation is **deterministic and rule-based**.
- ❌ No real secrets, no live account IDs (dummy `000000000000` is clearly marked).

## Local-only MVP scope

The MVP runs entirely on your machine. Optional external scanners (Checkov, OPA) are used
**if present** and skipped with a warning if not — the pipeline never fails just because a
tool is missing. `terraform validate` runs if `terraform` is on your `PATH`.

## Install

Requires Python **3.12+** and [Poetry](https://python-poetry.org/).

```bash
poetry env use 3.12      # match the mypy target; the repo pins python ^3.12
poetry install
```

> The console script is `cloudforge` (`poetry run cloudforge ...`).

## Quickstart

```bash
poetry run cloudforge generate examples/ci_cd_iam_chain.yaml --out out/scenario_001
poetry run cloudforge validate out/scenario_001
poetry run cloudforge report   out/scenario_001
```

`validate` prints fail-soft results, e.g.:

```
[PASS] scenario schema valid.
[PASS] graph schema valid.
[PASS] terraform validate.
[WARN] checkov scan. not found — skipping
[WARN] opa eval. not found — skipping
[PASS] ground-truth path exists.
[PASS] no forbidden permissions.
```

## Output structure

```
out/scenario_001/
├── scenario.yaml            # user intent (echoed)
├── graph.json               # generated scenario — SOURCE OF TRUTH
├── terraform/
│   ├── providers.tf  variables.tf  main.tf
│   ├── iam.tf        s3.tf          network.tf
├── expected_findings.json   # labeled findings (with ground_truth + remediation)
├── ground_truth_paths.json  # intended critical risk path(s)
├── scanner_results/
│   └── checkov.json         # written only if checkov is installed
├── opa_results.json         # written only if opa is installed
└── report.md                # human-facing explanation
```

**Source-of-truth hierarchy:** `scenario.yaml` (intent) → `graph.json` (truth) →
`terraform/` (artifact) → `scanner_results/` (observed) vs. `ground_truth_paths.json`
(expected) → `report.md` (explanation). Terraform is **never** the source of truth.

## The first scenario: `ci_cd_iam_chain`

A staging b2b_saas environment where a GitHub Actions OIDC identity assumes a DeployRole
that can `iam:PassRole` a RuntimeRole, and the RuntimeRole holds broad S3 read over a
sensitive customer-exports bucket:

```
github-actions-oidc → DeployRole → (iam:PassRole) RuntimeRole → (s3:Get*/List*) customer-exports
```

It ships one **critical** IAM chain, a **high** excessive-privilege finding, two **medium**
findings (missing S3 logging, a `0.0.0.0/0` security group), and one **benign
false-positive** (a public-looking bucket with a compensating control).

## Safety & scope statement

> Every generated scenario is for **local static analysis, scanner benchmarking, and
> defensive security training. It is not deployed and does not require cloud credentials.**
> The generator refuses destructive permissions (`iam:Delete*`, `s3:DeleteBucket`,
> `ec2:TerminateInstances`, `kms:ScheduleKeyDeletion`, `organizations:*`) — broad *read*
> grants are permitted only as explicitly-documented, intended misconfigurations.

## Roadmap

- **Now (MVP):** deterministic `TemplateGenerator`, one scenario family, fail-soft
  validators, ground-truth risk engine, report.
- **Next:** `MutationGenerator` (name/tag/resource variants), more scenario families,
  Checkov/OPA wired into CI.
- **Future (documented, not built):** `LLMGenerator`, `ModalBatchGenerator`,
  `DiffusionGraphGenerator` — all behind the same `ScenarioGenerator` interface. Local
  validators remain the source of truth regardless of the generation engine. See the
  [wiki](docs/wiki/Roadmap.md).

## Development

```bash
poetry run ruff check --fix && poetry run ruff format   # lint + format
poetry run mypy --strict app/                            # type check
poetry run pytest tests/cloudforge/ --cov=app            # tests (95%+ coverage)
```

## Documentation

Full docs are staged under [`docs/wiki/`](docs/wiki/) (mirroring the GitHub Wiki):
Home, Architecture, Scenario Schema, Graph Model, Validation Pipeline, Scenario Families,
Roadmap, Modal & Diffusion, Safety & Scope, and Template Feedback.

---

<sub>Built on an agentic Claude Code dev template; the agentic scaffolding is kept inert —
the deliverable is the local generator, not a multi-agent runtime.</sub>
