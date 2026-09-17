# Contributing

Product code is `app/cloudforge/`, `tests/cloudforge/`, `tests/security/`,
`examples/`, and `docs/wiki/`.

## Setup

Python 3.12+ and Poetry:

```bash
poetry env use 3.12
poetry install --with dev
PYTHONPATH=. .venv/bin/python -m app.cli version
```

If `.venv/bin/cloudforge` has a stale shebang, use `python -m app.cli`.

## Checks

```bash
poetry run ruff check app tests scripts
poetry run ruff format --check app tests scripts
poetry run mypy --strict app/
PYTHONPATH=. poetry run pytest tests/cloudforge tests/security tests/unit tests/integration tests/property -q --no-cov
```

Integration tests that call `validate` must force optional tools absent:

```python
monkeypatch.setattr(tool_probe, "detect_tool", lambda name: False)
```

Otherwise each test may download the AWS Terraform provider (~700MB).

## Adding a family

A family is one core fragment module and one example spec; see
[Adding a Family](docs/wiki/Adding-a-Family.md) for a worked example using the
`cloudforge new-family` scaffold.

## PRs

- Branch from `master`. Do not commit to `master`.
- Conventional commits (`feat:`, `fix:`, `docs:`, `test:`, `chore:`).
- Sign off each commit (`git commit --signoff`).
- Never `terraform apply`. Never add real credentials.
