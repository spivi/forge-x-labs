# Stress Test Plan

Prove `cloudforge` does not lie, deploy, leak, emit invalid artifacts, silently
lose ground truth, or export unsafe corpus data under hostile input and
malformed scanner output.

The 15-clause contract lives in
[`docs/testing/stress-contract.md`](../testing/stress-contract.md).

## Rule

When a stress test finds a real contract violation in shipped code: stop
expanding the suite, write a minimal reproducer, fix the guard, add
regression coverage, then continue.

A hostile input **rejected with a clear error** or **safely neutralized** is
the guarantee working, not a bug.

## Surfaces

| Surface | What it covers |
|---------|----------------|
| Graph / ground-truth / findings | property-based invariants |
| Terraform emitter | HCL injection, label collisions, path traversal |
| Mutation | determinism and risk preservation at scale |
| Scanner scoring | malformed, partial, unexpected checkov output |
| OPA policy | deny coverage |
| Learning corpus | registry, ingestion, export gate |
| Differential / metamorphic | cross-artifact consistency |
| CLI failure modes | no raw tracebacks, no fake success |
| Performance | measure, do not optimize |

Default `pytest` deselects `stress` and `internet`. Run them with
`pytest -m stress` or `pytest -m internet`.
