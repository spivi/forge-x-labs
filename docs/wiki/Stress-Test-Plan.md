# Stress-Test Plan — FXL-STRESS-1

**Goal:** prove `cloudforge` does not **lie, deploy, leak, generate invalid artifacts, silently
lose ground truth, or export unsafe/restricted corpus data** — under hostile input, scale, and
malformed external-tool output. This is hostile validation, not more unit testing.

The machine-checkable acceptance definition (15 clauses, S1–S15) lives in
[`docs/testing/stress-contract.md`](../testing/stress-contract.md). This page is the plan: the
surfaces, the phases, how to run each profile, and the fail-and-fix rule.

## The rule: stop and fix on a real bug

When a stress test reproduces a genuine contract violation in shipped code: **stop expanding
the suite, write a minimal reproducer, fix the guard, add regression coverage, then continue.**
A test that fails because the *test* is wrong (over-strict, mis-modeled input) is a test bug —
fix the test. A hostile input **rejected with a clear error** or **safely neutralized** is the
guarantee working, not a bug — assert it.

During the epic, a finder captures a real violation as a `@pytest.mark.xfail(strict=True)` with a
reproducer first (so the fast suite stays green and nothing is hidden), then the fix flips it to
a passing regression.

## The nine surfaces

| # | Surface | Ticket | Clauses |
|---|---------|--------|---------|
| 1 | Graph / ground-truth / finding invariants (property-based) | STRESS-2 | S4 S5 S6 S7 |
| 2 | Terraform emitter — HCL injection, label collisions, traversal | STRESS-3 | S2 S3 S7 |
| 3 | Mutation — determinism + risk preservation at scale | STRESS-4 | S10 S11 |
| 4 | Scanner scoring — malformed / partial / unexpected output | STRESS-5 | S12 |
| 5 | OPA policy — deny coverage | STRESS-6 | S7 S9 S13 S14 |
| 6 | Learning corpus — registry + ingestion + export gate | STRESS-7 | S8 S9 |
| 7 | Differential + metamorphic — cross-artifact consistency | STRESS-8 | S4 S5 S14 S15 |
| 8 | CLI failure modes | STRESS-9 | S1 S15 |
| 9 | Performance / scale (measure, don't optimize) | STRESS-10 | — |

Plus STRESS-11 (markers + `hypothesis` + CI profiles) and STRESS-12 (results report + go/no-go).

## Markers

Registered in `pyproject.toml` (`[tool.pytest.ini_options] markers`):

- `unit`, `security`, `property`, `integration` — included in the default/fast run.
- `internet` — opt-in real-network learning-corpus fetch tests (`-m internet`).
- `stress` — slow, many-seed/large-scale stress (the full 1,000-seed sweeps); opt-in (`-m stress`).
- `slow` — heavy/long-running; the pre-push backstop deselects these.

Default `addopts` deselects `stress` and `internet`, so `pytest` stays fast and offline.

## Profiles — how to run

**Fast** (every PR — no terraform/checkov/opa/network required):

```bash
ruff check app/ tests/cloudforge/ tests/security/
mypy app/ --ignore-missing-imports
pytest tests/ -q --hypothesis-profile=ci        # unit + security + property (deterministic)
```

**Tool-backed** (when the optional tools are installed — each guards on presence):

```bash
terraform init -backend=false && terraform validate -json     # in a scenario's terraform/ dir
checkov -d <scenario>/terraform -o json --framework terraform
opa test policies/ -v
opa test policies/ --coverage --format=json                   # policy coverage
```

**Nightly / manual stress** (opt-in, slow):

```bash
pytest -m stress --hypothesis-profile=ci        # 1,000-seed mutation sweep, 5,000-example property runs
python scripts/stress_benchmark.py              # scenario + corpus scaling measurement (STRESS-10)
```

See [`docs/testing/ci-profiles.md`](../testing/ci-profiles.md) for the full CI-job wiring.

## Determinism

Property tests run under the `ci` Hypothesis profile (`derandomize=True`) so they are
reproducible and non-flaky. Mutation stress asserts same-seed → byte-identical output. Any
non-determinism a stress run surfaces is a bug worth reporting.

## Results

The epic's verdict — the bug ledger (found → reproducer → fix → regression), the coverage status
of all 15 clauses, remaining weak points, and a go/no-go for the next product phase — is published
in [`docs/testing/stress-results.md`](../testing/stress-results.md) (STRESS-12).
