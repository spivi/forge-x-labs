# Modal & Diffusion — Future Integration

> **Status: documented, not built.** None of this exists in the MVP. Modal is **not** a
> dependency and must never become a core one.

## The intended shape

```
local CLI (cloudforge)
   → optional Modal batch generator      # fan out many scenarios on Modal
   → optional Modal GPU graph generator  # learned/diffusion graph proposals
   → local validators remain the source of truth
```

Modal is an **optional generation engine**, not part of the core pipeline. Any Modal or
GPU work would live behind the same `ScenarioGenerator` interface used by
`TemplateGenerator`, so the pipeline, validators, and report are unaffected.

## Why validators stay local

A generative engine (LLM or diffusion) can propose plausible but wrong graphs. The value of
cloudforge is the **ground truth**, so a generated graph is only accepted after the local
risk engine (and, where available, checkov/OPA) validate it. Generation cleverness never
outranks validation.

## Non-goals for the foreseeable future

Real diffusion training, GPU jobs, Modal deployment, Kubernetes, multi-cloud, runtime
telemetry, and any cloud deployment are explicitly out of scope until deliberately
prioritized. The MVP is deterministic and local by design.
