"""CLI entry point.

API-first design: CLI acts as a client to the internal logic layer.
Business logic lives in services, not here.
"""
from __future__ import annotations

import typer
from rich.console import Console

app = typer.Typer(help="{{PROJECT_DESCRIPTION}}")
console = Console()


@app.command()
def hello(name: str = "world") -> None:
    """Say hello."""
    console.print(f"Hello, [bold green]{name}[/bold green]!")


if __name__ == "__main__":
    app()
