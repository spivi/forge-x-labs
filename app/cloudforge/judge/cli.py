"""CLI: judge a student writeup against the instructor key using Jev."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from dotenv import load_dotenv
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from app.cloudforge.errors import CloudforgeError
from app.cloudforge.io.loaders import load_json, load_yaml
from app.cloudforge.judge.engine import judge_rationale
from app.cloudforge.judge.models import JudgeVerdict
from app.cloudforge.lab.paths import LabPaths
from app.cloudforge.lab.submission import LabSubmission
from app.cloudforge.models.findings import ExpectedFindings, GroundTruthPaths
from app.cloudforge.models.graph import ScenarioGraph

console = Console()
_CLI_ERRORS: tuple[type[Exception], ...] = (CloudforgeError, ValidationError, OSError)


def register_judge_command(app: typer.Typer) -> None:
    """Attach ``cloudforge judge`` to the root app."""
    app.command("judge")(judge)


def judge(
    lab_dir: Annotated[Path, typer.Argument(help="Directory written by cloudforge lab.")],
    rationale: Annotated[
        Path | None,
        typer.Option("--rationale", help="Plain-text student writeup."),
    ] = None,
    submission: Annotated[
        Path | None,
        typer.Option("--submission", help="Guess YAML; uses optional rationale field."),
    ] = None,
) -> None:
    """Score a free-text rationale with Jev. Exact path matching stays in grade."""
    load_dotenv()
    try:
        text = _rationale_text(rationale, submission)
        graph, findings, paths = _load_instructor(lab_dir)
        verdict = judge_rationale(text, graph, findings, paths)
    except _CLI_ERRORS as exc:
        console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    _print_verdict(verdict)


def _rationale_text(rationale: Path | None, submission: Path | None) -> str:
    if rationale is not None:
        return rationale.read_text(encoding="utf-8")
    if submission is None:
        raise CloudforgeError("pass --rationale FILE or --submission FILE")
    guess = LabSubmission.model_validate(load_yaml(submission))
    if not guess.rationale:
        raise CloudforgeError("submission has no rationale field")
    return guess.rationale


def _load_instructor(
    lab_dir: Path,
) -> tuple[ScenarioGraph, ExpectedFindings, GroundTruthPaths]:
    paths = LabPaths.from_dir(lab_dir)
    instructor = paths.instructor
    graph_file = instructor / "graph.json"
    findings_file = instructor / "expected_findings.json"
    truth_file = instructor / "ground_truth_paths.json"
    missing = [p for p in (graph_file, findings_file, truth_file) if not p.is_file()]
    if missing:
        raise CloudforgeError(f"missing instructor artifacts: {missing[0]}")
    graph = ScenarioGraph.model_validate(load_json(graph_file))
    findings = ExpectedFindings.model_validate(load_json(findings_file))
    truth = GroundTruthPaths.model_validate(load_json(truth_file))
    return graph, findings, truth


def _print_verdict(verdict: JudgeVerdict) -> None:
    table = Table(title=f"Jev rationale judge ({verdict.model})")
    table.add_column("Signal")
    table.add_column("Value")
    table.add_row("names entry", f"{verdict.names_entry:.3f}")
    table.add_row("names identity hop", f"{verdict.names_identity_hop:.3f}")
    table.add_row("names sink", f"{verdict.names_sink:.3f}")
    table.add_row("completeness", f"{verdict.completeness:.3f} ({verdict.completeness_label})")
    table.add_row("semantic hit", "yes" if verdict.semantic_hit else "no")
    table.add_row("instructor review", "yes" if verdict.needs_review else "no")
    console.print(table)
