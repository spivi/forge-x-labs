# Forge X Labs — Wiki Home

**`cloudforge`** is a local-first cloud-misconfiguration **scenario generator**. It
produces realistic, labeled, **validated** cloud-risk scenarios — as risk graphs plus
never-applied Terraform, ground truth, and a report — for scanner benchmarking, security
training, and prioritization research.

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
| [Scenario Families](Scenario-Families) | `ci_cd_iam_chain` and how to add families |
| [Roadmap](Roadmap) | What's next; the generator extension seam |
| [Modal & Diffusion Future Integration](Modal-and-Diffusion-Future-Integration) | Optional future engines |
| [Safety & Scope](Safety-and-Scope) | Local-only guarantees, forbidden permissions |
| [Template Feedback](Template-Feedback) | Feedback on the base agentic template |
| [Learning Corpus](Learning-Corpus) | The FXL-E2 data pipeline: fetch → ingest → normalize → validate → dedup → score → export |
| [Source Registry](Source-Registry) | The corpus allow-list: schema, governance, source tiers |
| [Risk Pattern Ontology](Risk-Pattern-Ontology) | The `RiskPattern` fields, enums, graph-fragment compatibility |
| [Source Adapters](Source-Adapters) | The `PatternAdapter` protocol and the 3 shipped adapters |
| [Provenance and Licensing](Provenance-and-Licensing) | Provenance model, reuse-status vocabulary, FXL-D007 |
| [Corpus Quality Scoring](Corpus-Quality-Scoring) | Quality/realism scoring design, dedup key, export gate |
| [Future Diffusion Training](Future-Diffusion-Training) | How the corpus prepares (but does not implement) diffusion |

## Scope in one line

Local-only · no AWS creds · never `terraform apply` · no real secrets · defensive only ·
deterministic generation first · validators + ground truth over generation cleverness.
