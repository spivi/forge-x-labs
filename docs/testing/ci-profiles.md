# CI Profiles & Test Markers

**Ticket:** FXL-STRESS-11 (#113) · **Epic:** FXL-STRESS-1 (Break cloudforge before expanding it)

This document formalizes the test markers, hypothesis profiles, and CI profiles that enable fast feedback (unit/security/property tests) while keeping stress tests and tool validation opt-in.

## Test Markers

All markers are registered in `pyproject.toml` under `[tool.pytest.ini_options] markers`:

| Marker | Purpose | Default | Profile |
|--------|---------|---------|---------|
| `unit` | Fast unit tests (no external deps) | Included | Fast |
| `security` | Security validation tests (auth, injection, CORS) | Included | Fast |
| `property` | Property-based tests via hypothesis | Included | Fast |
| `integration` | Integration tests (multiple components, light I/O) | Included | Fast |
| `internet` | Real-network tests (corpus fetcher, #74) | Deselected by default (`-m 'not internet'`) | Manual/Nightly |
| `stress` | Adversarial stress tests (mutation, corpus, security-corpus) | Deselected by default (`-m 'not stress'`) | Nightly/Manual |
| `slow` | Heavy/long-running tests | Included (pre-push backbone excludes with `-m 'not slow'`) | Nightly |

The default `addopts` in `pyproject.toml` deselects `stress` and `internet`:
```toml
addopts = "--cov=app --cov-report=term-missing --cov-fail-under=80 -m 'not stress and not internet'"
```

This ensures **every PR and default local run is fast**.

## Hypothesis Profiles

Two profiles are registered in `tests/conftest.py`:

### `ci` Profile (Deterministic)

```python
settings.register_profile("ci", derandomize=True, deadline=None)
```

**Used by:** CI fast profile, reproducible local stress runs.
**Properties:**
- `derandomize=True` ensures **byte-identical output** across runs (S10 — cloudforge stress clause).
- `deadline=None` removes flakiness from test infrastructure differences.
- No flakiness from wall-clock, PID, or global RNG state.

**Invocation:**
```bash
pytest tests/ --hypothesis-profile=ci
```

### `dev` Profile (Exploratory)

```python
settings.register_profile("dev", deadline=None)
```

**Used by:** Local development, discovering edge cases via randomization.
**Properties:**
- Allows randomization for deeper coverage discovery.
- `deadline=None` prevents deadline flakiness in rapid iteration.
- Reusable across multiple runs (`hypothesis.seed()` per test).

**Invocation:**
```bash
# Load the profile manually in tests or via CLI:
pytest tests/ --hypothesis-profile=dev
```

## CI Profiles

### 1. Fast Profile (Every PR)

**Runs:** `lint-and-type-check` → `test-fast` (parallel to tools below if present).

**Commands:**
```bash
# Lint + format check
ruff check app/ tests/cloudforge/ tests/security/
ruff format --check app/ tests/cloudforge/ tests/security/

# Type checking
mypy app/ --ignore-missing-imports

# Tests (unit/security/property; stress+internet deselected by default)
pytest tests/ --cov=app --cov-report=xml -q --hypothesis-profile=ci
```

**Markers:** `unit`, `security`, `property`, `integration`  
**Excluded:** `stress`, `internet`  
**External deps:** None (hypothesis is a dev dependency, not a tool)  
**Duration:** < 2 minutes  
**Coverage gate:** 80% minimum  

### 2. Tools Profile (When Present)

**Runs:** `test-tools` (parallel to fast profile).

**Commands:**
```bash
# Terraform validation (if terraform is installed)
terraform init -backend=false
terraform validate -json

# Checkov scanning (if checkov is installed)
checkov -d app/ -o json --framework terraform

# OPA policy tests (if opa is installed)
opa test policies/ -v
```

**Design:**
- Each tool is **guarded on presence** — if the tool is not installed, that check is skipped.
- Tool *presence* issues (missing/PATH not set) → WARN (S13).
- Tool *syntax/config* errors → FAIL (S14).
- No blocker to fast CI — runs in parallel.

**Status in this repo:** Tools are optional scaffolding. The workflow checks for their presence but does not fail if absent.

### 3. Nightly / Manual Stress Profile

**Runs:** Manual trigger or scheduled nightly (not in default CI).

**Commands:**
```bash
# Mutation stress runner (FXL-N3)
pytest tests/ -m stress -q --hypothesis-profile=ci

# Future: corpus stress, security-corpus mutation (FXL-STRESS-4, FXL-STRESS-10)
```

**Markers:** `stress`, `slow`, `internet` (opt-in)  
**External deps:** None (all stress tests are synthetic/generated)  
**Duration:** 30+ minutes  
**Coverage gate:** 80% minimum (same as fast)  

## Local Usage

### Run the Fast Profile Locally

```bash
# All tests except stress/internet (same as CI fast profile)
pytest tests/ -q --hypothesis-profile=ci

# Or via marker:
pytest tests/ -m 'not stress and not internet' --hypothesis-profile=ci
```

### Run Property Tests Only

```bash
pytest tests/ -m property --hypothesis-profile=ci
```

### Run Stress Tests Locally

```bash
# All stress tests with deterministic hypothesis
pytest tests/ -m stress --hypothesis-profile=ci

# Or with dev profile (randomized):
pytest tests/ -m stress --hypothesis-profile=dev
```

### Run Integration + Slow Tests

```bash
pytest tests/ -m 'integration or slow' --hypothesis-profile=ci
```

## Integration with the Stress Contract

- **S10** (Byte-identical output): `--hypothesis-profile=ci` + `derandomize=True` ensures reproducibility.
- **S11** (Risk invariants across seeds): Property tests can randomize with `--hypothesis-profile=dev` to discover variations, then confirm invariants hold.
- **S13/S14** (Tool fail-soft/hard): The tools profile guards tool presence and distinguishes env errors (WARN) from syntax errors (FAIL).

## Migration Notes

- Existing markers (`stress`, `internet`, `slow`) are preserved in pyproject.toml.
- New markers (`unit`, `security`, `property`, `integration`) are added — use them when writing new tests.
- Default behavior unchanged: bare `pytest` still runs fast, excludes stress/internet.
- `hypothesis` is a dev dependency; it does not bloat production.
- CI profile determinism (S10) is non-breaking — tests previously written remain green.
