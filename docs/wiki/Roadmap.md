# Roadmap

## Now — MVP (delivered)

- Deterministic `TemplateGenerator`, one family (`ci_cd_iam_chain`).
- Full pipeline: `generate → validate → report`.
- Fail-soft validators (schema · terraform · checkov · opa) + stdlib graph-risk engine.
- Ground truth (paths + expected findings) machine-checked against the graph.

## Next

- **`MutationGenerator`** — name/tag/resource variants for scenario diversity, behind the
  `ScenarioGenerator` interface (issue #14).
- **More scenario families** (see [Scenario Families](Scenario-Families)).
- **Checkov/OPA in CI** — currently fail-soft locally; wire them into the pipeline when the
  runners have the tools.
- **OPA over Terraform plan** — today the Rego evaluates `graph.json`; add plan support.

## The extension seam

Every future generator implements one method:

```python
class ScenarioGenerator(Protocol):
    def generate(self, spec: ScenarioSpec) -> ScenarioBundle: ...
```

The pipeline, validators, and report are engine-agnostic — they only ever read the graph
and its ground truth. This keeps future engines **additive**.

## Future engines (not in v1)

Documented, not built. Do not start these until trainers ask after v1.

- `LLMGenerator` — propose graphs from natural-language scenario briefs.
- `ModalBatchGenerator` / `DiffusionGraphGenerator` — see
  [Modal & Diffusion Future Integration](Modal-and-Diffusion-Future-Integration).

**Invariant across all of them:** local validators remain the source of truth. A generated
graph is only trustworthy once the risk engine (and, where available, checkov/OPA) confirm
it.
