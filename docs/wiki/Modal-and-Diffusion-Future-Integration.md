# Modal and Diffusion (future)

**Not in v1.** Documented, not built. Modal is not a dependency and must not
become a core one.

Intended shape, if anyone asks later:

```
local CLI (cloudforge)
   -> optional batch generator
   -> optional learned/diffusion graph proposals
   -> local validators remain the source of truth
```

Any such engine would implement the same `ScenarioGenerator` interface as
`TemplateGenerator` and `GraphComposer`. A generated graph is only accepted
after the local risk engine (and, where available, checkov/OPA) validate it.
