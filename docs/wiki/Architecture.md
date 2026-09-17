# Architecture

## Source of truth

```
scenario.yaml            user intent
   |  generate
   v
graph.json               generated scenario  -- SOURCE OF TRUTH
   |  compile
   v
terraform/               artifact (validated statically, NEVER applied)
   |  scan
   v
scanner_results/         observed local scanner output
                         vs.
ground_truth_paths.json  expected security reality
   |  render
   v
report.md                human-facing explanation
```

Terraform is a **compiled artifact**, never the source of truth. The graph and
the ground truth are authored together so the scenario is machine-checkable.

## Package layout (`app/cloudforge/`)

```
app/
  cli.py                     re-export of the Typer app (entry point)
  cloudforge/
    cli.py                   generate / validate / report / version
    constants.py             filenames, severities, forbidden permission patterns
    errors.py                typed exceptions
    models/                  scenario, graph, findings (Pydantic v2)
    generate/                template, composer, mutation, fragments
    pipeline/                artifact writer, Terraform emitter
    validate/                orchestrator, graph-risk, optional scanners
    report/                  markdown report
    lab/                     student/instructor packs, grade, workbench
    variation/               diversity harness
    learn/                   corpus fetch / ingest / export
    io/                      paths and loaders
policies/scenario.rego       OPA policy over graph.json
examples/*.yaml
```

## Command flow

- **generate**: load `scenario.yaml`, run template or composer, write the
  artifact tree (graph, findings, paths, Terraform).
- **validate**: reconstruct the bundle from disk and run fail-soft checks
  (see [Validation Pipeline](Validation-Pipeline.md)).
- **report**: reload artifacts and write `report.md`.
- **lab / grade / roundtable**: split student vs instructor, score a guessed
  path, or write a three-cloud SOC tabletop pack.

## Design principles

- Graph is truth. Every other artifact derives from or is checked against it.
- Fail-soft: optional tooling never blocks the pipeline; only real failures do.
- New generators implement `ScenarioGenerator`. The rest of the pipeline stays
  the same.
