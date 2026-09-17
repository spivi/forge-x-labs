# Wiki home

**`cloudforge`** is a local-first generator of **validated, never-applied
cloud misconfig labs**. Each student gets a unique copy with a hidden answer
key. No cloud account required.

The value is labeled, validated cloud-risk **graphs** with machine-checkable
ground truth, not clever Terraform generation.

## Pipeline

```
scenario.yaml  --generate-->  graph.json (+ terraform/, findings, ground truth)
graph.json     --validate-->  schema, terraform, checkov, opa, graph-risk engine
scenario dir   --report---->  report.md
```

```bash
cloudforge generate examples/ci_cd_iam_chain.yaml --out out/scenario_001
cloudforge validate out/scenario_001
cloudforge report   out/scenario_001
```

## Pages

| Page | What it covers |
|------|----------------|
| [Architecture](Architecture.md) | Module layout, pipeline, source of truth |
| [Scenario Schema](Scenario-Schema.md) | The `scenario.yaml` input contract |
| [Graph Model](Graph-Model.md) | Node and edge types, invariants |
| [Validation Pipeline](Validation-Pipeline.md) | Fail-soft checks, risk engine, exit policy |
| [Labs](Labs.md) | Student/instructor pack, grade, cohort, roundtable |
| [Curriculum](Curriculum.md) | A first week, session by session |
| [Scenario Families](Scenario-Families.md) | Shipped families |
| [Adding a Family](Adding-a-Family.md) | Worked example: one fragment, one spec, the scaffold |
| [Roadmap](Roadmap.md) | What shipped, what is next |
| [Safety and Scope](Safety-and-Scope.md) | Local-only guarantees, forbidden permissions |
| [Learning Corpus](Learning-Corpus.md) | Data pipeline (not a training loop) |
| [Source Registry](Source-Registry.md) | Allow-list and reuse rules |
| [Source Adapters](Source-Adapters.md) | How sources become patterns |
| [Provenance and Licensing](Provenance-and-Licensing.md) | No provenance, no corpus |
| [Risk Pattern Ontology](Risk-Pattern-Ontology.md) | `RiskPattern` fields |
| [Corpus Quality Scoring](Corpus-Quality-Scoring.md) | Rubric scores, not a learned model |
| [Stress Test Plan](Stress-Test-Plan.md) | Hostile validation of the pipeline |

## Scope in one line

Local only. No cloud credentials. Never `terraform apply`. No real secrets.
Defensive only. Deterministic generation first. Validators and ground truth
over generation cleverness.
