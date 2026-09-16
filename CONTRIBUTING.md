# Contributing

Product code is `app/cloudforge/`, `tests/cloudforge/`, `tests/security/`,
`examples/`, and `docs/wiki/`.

`.dev-context/`, `lemmings/`, `flavors/`, `scripts/` (except product tests
under `tests/scripts/`), and `.claude/` are **maintainer scaffolding** for
the internal agent pipeline. Do not "clean them up" in drive-by PRs.

## Setup

Python 3.12+ and Poetry:

```bash
poetry env use 3.12
poetry install
PYTHONPATH=. .venv/bin/python -m app.cli version
```

If `.venv/bin/cloudforge` has a stale shebang, use `python -m app.cli`.

## Checks

```bash
ruff check --fix && ruff format
mypy --strict app/
PYTHONPATH=. .venv/bin/pytest tests/cloudforge tests/security -q --no-cov
```

Integration tests that call `validate` must force optional tools absent:

```python
monkeypatch.setattr(tool_probe, "detect_tool", lambda name: False)
```

Otherwise each test may download the AWS Terraform provider (~700MB).

## PRs

- Branch: `feat/FXL-<n>-short-desc` or `fix/FXL-<n>-short-desc`
- Conventional commits with `--signoff`
- Do not commit to `master`
- Never `terraform apply`; never add real credentials
