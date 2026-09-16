"""Typer handlers for ``cloudforge lab`` and ``cloudforge grade``."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError
from rich.console import Console

from app.cloudforge.errors import CloudforgeError
from app.cloudforge.io.loaders import load_json, load_yaml
from app.cloudforge.lab.grade import grade_submission
from app.cloudforge.lab.pack import LabRequest, write_lab
from app.cloudforge.lab.paths import LabPaths
from app.cloudforge.lab.submission import GradeResult, LabSubmission
from app.cloudforge.models.scenario import ScenarioSpec

console = Console()
_CLI_ERRORS: tuple[type[Exception], ...] = (CloudforgeError, ValidationError, OSError)


def register_lab_commands(app: typer.Typer) -> None:
    """Attach ``lab`` and ``grade`` to the root Typer app."""
    app.command("lab")(lab)
    app.command("grade")(grade)


def lab(
    scenario: Annotated[Path, typer.Argument(help="Path to a scenario YAML file.")],
    out: Annotated[Path, typer.Option("--out", help="Lab directory (student/ + instructor/).")],
    seed: Annotated[int, typer.Option("--seed", help="Composer seed (deterministic).")] = 0,
    engine: Annotated[str, typer.Option("--engine", help="template or composer.")] = "composer",
) -> None:
    """Write a student pack (no answer key) and an instructor pack (grade key)."""
    try:
        spec = ScenarioSpec.model_validate(load_yaml(scenario))
        write_lab(LabRequest(spec=spec, seed=seed, engine=engine), LabPaths.from_dir(out))
    except _CLI_ERRORS as exc:
        console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    console.print(f"[green]lab[/green] student={out / 'student'} instructor={out / 'instructor'}")


def grade(
    lab_dir: Annotated[Path, typer.Argument(help="Directory written by ``cloudforge lab``.")],
    submission: Annotated[Path, typer.Option("--submission", help="Student guess YAML.")],
) -> None:
    """Score a guess against instructor/grade_key.json. Wrong answers still exit 0."""
    try:
        result = _grade_lab(lab_dir, submission)
    except _CLI_ERRORS as exc:
        console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    console.print(
        f"paths hit {len(result.path_hits)} miss {len(result.path_misses)}  "
        f"findings hit {len(result.finding_hits)} miss {len(result.finding_misses)}  "
        f"extras {len(result.extras)}"
    )


def _grade_lab(lab_dir: Path, submission_path: Path) -> GradeResult:
    paths = LabPaths.from_dir(lab_dir)
    if not paths.grade_key.is_file():
        raise CloudforgeError(f"missing instructor key at {paths.grade_key}")
    key = load_json(paths.grade_key)
    guess = LabSubmission.model_validate(load_yaml(submission_path))
    return grade_submission(key, guess)
