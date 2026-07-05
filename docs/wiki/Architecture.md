# Architecture

## Source-of-truth hierarchy

```
scenario.yaml            user intent
   │  generate
   ▼
graph.json               generated scenario  ── SOURCE OF TRUTH
   │  compile
   ▼
terraform/               artifact (validated statically, NEVER applied)
   │  scan
   ▼
scanner_results/         observed local scanner output
                         vs.
ground_truth_paths.json  expected security reality
   │  render
   ▼
report.md                human-facing explanation
```

Terraform is a **compiled artifact**, never the source of truth. The graph and the ground
truth are authored together so the scenario is machine-checkable.

## Package layout (`app/cloudforge/`)

The product lives under the template's `app/` package (see decision **FXL-D001**) so CI
(`--cov=app`, `mypy app/`) and the console-script contract (`cloudforge = "app.cli:app"`)
work with zero CI edits.

```
app/
  cli.py                     re-export of the Typer app (entry point)
  cloudforge/
    cli.py                   Typer commands: generate / validate / report / version
    constants.py             filenames, severities, forbidden/allowed permission patterns, banner
    errors.py                typed exceptions
    models/                  Pydantic v2: scenario.py, graph.py, findings.py
    generate/                base.py (ScenarioGenerator), template_generator.py, ci_cd_iam_chain.py
    pipeline/                artifacts.py (writes the tree), terraform_emitter.py, terraform_blocks.py
    validate/                orchestrator.py, graph_risk.py, external_scans.py, schema_checks.py,
                             tool_probe.py, results.py
    report/                  renderer.py, sections.py
    io/                      paths.py (path contract), loaders.py (typed read/write)
policies/scenario.rego       OPA policy over graph.json
examples/ci_cd_iam_chain.yaml
```

## Command flow

- **generate** — load + validate `scenario.yaml` → `TemplateGenerator.generate()` returns a
  `ScenarioBundle` (graph + findings + ground truth) → `ScenarioArtifacts.write_all()`
  serializes the whole output tree, including the six `.tf` files.
- **validate** — `run_validations()` reconstructs the bundle from disk and runs the
  fail-soft checks (see [Validation Pipeline](Validation-Pipeline)).
- **report** — `ReportRenderer` re-loads the artifacts (works standalone) and joins the
  section builders into `report.md`.

## Design principles

- **Small, single-purpose modules** (≤200 lines) and functions (≤30 lines).
- **Graph is truth**; every other artifact derives from or is checked against it.
- **Fail-soft**: optional tooling never blocks the pipeline; only real failures do.
- **Extensible generation**: new engines implement `ScenarioGenerator`; the pipeline is
  unchanged.
