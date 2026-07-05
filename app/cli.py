"""Console-script entry point.

Kept thin on purpose: the template's ``[tool.poetry.scripts]`` maps the
``cloudforge`` command to ``app.cli:app``. The real Typer application lives in
``app.cloudforge.cli`` so all business logic stays inside the product sub-package.
"""

from __future__ import annotations

from app.cloudforge.cli import app

__all__ = ["app"]

if __name__ == "__main__":  # pragma: no cover - manual invocation only
    app()
