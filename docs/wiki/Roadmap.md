# Roadmap

## v1.0 (shipped)

- 12 AWS scenario families.
- Pipeline: `generate -> validate -> report`.
- Trainer loop: `lab` / `grade` / cohort / `challenge` workbench.
- Fail-soft validators (schema, terraform, checkov, opa) plus a stdlib
  graph-risk engine.
- Ground truth (paths + expected findings) machine-checked against the graph.
- Variation harness with a diversity gate.
- Learning corpus CLI (data only, no model training).

## Next

Deeper Azure/GCP/K8s HCL (role assignments, IRSA trust policy conditions) and
more families. `cloudforge judge` stays opt-in.

## The extension seam

Every future generator implements one method:

```python
class ScenarioGenerator(Protocol):
    def generate(self, spec: ScenarioSpec) -> ScenarioBundle: ...
```

The pipeline, validators, and report only ever read the graph and its ground
truth. New engines stay additive.

## Not in v1

Documented, not built. Do not start these until trainers ask.

- `LLMGenerator`: propose graphs from natural-language briefs.
- Modal / diffusion graph generators. See
  [Modal and Diffusion](Modal-and-Diffusion-Future-Integration.md).

Local validators remain the source of truth for any of those.
