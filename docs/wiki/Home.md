# Forge X Labs — Wiki Home

**`cloudforge`** is a local-first generator of **validated, never-applied AWS
misconfig labs** — unique per student, with a hidden answer key. No cloud
account required. Scanner scoring is a property of every lab, not the headline.

> **Core thesis:** the value is in labeled, validated cloud-risk **graphs** with
> machine-checkable ground truth — not in clever Terraform generation.

## Pipeline at a glance

```
scenario.yaml ──generate──▶ graph.json (+ terraform/, findings, ground truth)
graph.json    ──validate──▶ schema · terraform · checkov · opa · graph-risk engine
scenario dir  ──report────▶ report.md
```

```bash
cloudforge generate examples/ci_cd_iam_chain.yaml --out out/scenario_001
cloudforge validate out/scenario_001
cloudforge report   out/scenario_001
```

## Pages

| Page | What it covers |
|------|----------------|
| [Architecture](Architecture) | Module layout, pipeline flow, source-of-truth hierarchy |
| [Scenario Schema](Scenario-Schema) | The `scenario.yaml` input contract |
| [Graph Model](Graph-Model) | Node/edge types, metadata, self-consistency invariants |
| [Validation Pipeline](Validation-Pipeline) | Fail-soft checks, the risk engine, exit policy |
| [Labs](Labs) | Student/instructor pack, grade, cohort (FXL-D010) |
| [Scenario Families](Scenario-Families) | Shipped families and how to add one |
| [Roadmap](Roadmap) | What's next; the generator extension seam |
| [Safety & Scope](Safety-and-Scope) | Local-only guarantees, forbidden permissions |
| [Learning Corpus](Learning-Corpus) | Data pipeline (not a training loop) |
| [Source Registry](Source-Registry) | Allow-list, governance, source tiers |
| [Modal & Diffusion Future Integration](Modal-and-Diffusion-Future-Integration) | **Not in v1** |
| [Future Diffusion Training](Future-Diffusion-Training) | **Not in v1** |

## Scope in one line

Local-only · no AWS creds · never `terraform apply` · no real secrets · defensive only ·
deterministic generation first · validators + ground truth over generation cleverness.
