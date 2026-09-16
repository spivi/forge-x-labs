# CI profiles and test markers

Default `pytest` is the fast profile: unit, security, property, and
integration tests. Stress and real-network tests are opt-in.

## Markers

| Marker | Purpose | Default |
|--------|---------|---------|
| `unit` | Fast unit tests | included |
| `security` | Security validation | included |
| `property` | Hypothesis property tests | included |
| `integration` | Multi-component, light I/O | included |
| `internet` | Real-network corpus fetch | deselected |
| `stress` | Adversarial mutation / corpus stress | deselected |
| `slow` | Heavy tests | included in full suite |

```toml
addopts = "--cov=app --cov-report=term-missing --cov-fail-under=80 -m 'not stress and not internet'"
```

## Hypothesis profiles

Registered in `tests/conftest.py`:

- `ci`: `derandomize=True`, `deadline=None`. Byte-identical across runs.
- `dev`: randomized, `deadline=None`. Local exploration.

```bash
pytest tests/ --hypothesis-profile=ci
pytest tests/ -m stress --hypothesis-profile=ci
pytest tests/ -m internet
```

## CI jobs

1. **Lint and types:** ruff + mypy on `app/` and product tests.
2. **Fast tests:** `pytest tests/ --hypothesis-profile=ci` (stress/internet off).
3. **Optional tools:** terraform / checkov / opa if present on the runner.
   Missing tools are skipped, not a fail.

Coverage gate: 80%.
