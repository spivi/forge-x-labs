---
name: project-init
description: "Scaffold new Python projects with varying complexity (basic, cli, fastapi-modular). Generates pyproject.toml, pre-commit config, and project structure. Use when: /init, scaffold project, new project, project init, create project, bootstrap, start new project."
---

# Project Init Skill

Scaffold project structures tailored to specific needs while enforcing core template standards.

## Core Templates (All Flavors)

Every project MUST include:
- `pyproject.toml`: Modern Python project configuration
- `.gitignore`: Standard Python and tool-specific ignores
- `.pre-commit-config.yaml`: Ruff linting and formatting
- `.env.example`: Environment variable templates
- `README.md`: Project overview and setup instructions

## Flavors

### 1. Basic (Default)
Minimal structure for scripts, data analysis, or simple tools.
```
<project_name>/
├── app/
│   └── __init__.py
├── tests/
│   └── __init__.py
└── (Core Templates)
```

### 2. CLI
For command-line tools following the API-first rule (logic in services, CLI as client).
```
<project_name>/
├── app/
│   ├── __init__.py
│   ├── cli.py                   # Typer/Click entry point
│   ├── core/
│   │   └── config.py            # Settings
│   └── services/                # Reusable business logic
├── tests/
│   └── __init__.py
└── (Core Templates)
```

### 3. FastAPI Modular (Existing)
Full web application structure with defined layers.
```
<project_name>/
├── app/
│   ├── main.py, config.py, database.py
│   ├── api/ v1/ router.py, deps.py
│   ├── models/, schemas/, repositories/, services/, core/
├── tests/
│   ├── conftest.py, factories/
├── alembic/
└── (Core Templates)
```

## Setup Instructions

1. Use `setup.sh <project_name>` from the dev-template root to bootstrap the `.dev-context`.
2. Generate the selected flavor structure in the root.
3. Ensure `pyproject.toml` dependencies match the flavor:
   - `basic`: `ruff`, `pytest`
   - `cli`: `basic` + `typer`, `rich`
   - `fastapi-modular`: `basic` + `fastapi`, `sqlalchemy`, `alembic`, `pydantic-settings`

## Validation

- Standard files (`.gitignore`, etc.) are present and correctly configured.
- `app/` structure matches the requested flavor.
- All code follows the rules in `.dev-context/rules/`.
