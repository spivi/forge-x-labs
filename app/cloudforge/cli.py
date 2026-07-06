"""The ``cloudforge`` Typer application: generate / validate / report.

Commands are thin — they load input, call the generate/validate/report modules, and
print results. All logic lives in the sub-packages so it stays reusable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from app.cloudforge import __version__
from app.cloudforge.errors import CloudforgeError
from app.cloudforge.generate.base import ScenarioBundle
from app.cloudforge.generate.mutation_generator import MutationGenerator
from app.cloudforge.generate.template_generator import TemplateGenerator
from app.cloudforge.io.loaders import load_yaml
from app.cloudforge.io.paths import ScenarioPaths
from app.cloudforge.learn.cli import learn_app
from app.cloudforge.models.scenario import ScenarioSpec
from app.cloudforge.pipeline.artifacts import ScenarioArtifacts
from app.cloudforge.report.renderer import ReportRenderer
from app.cloudforge.validate.orchestrator import run_validations
from app.cloudforge.validate.results import Status

app = typer.Typer(help="Local-first cloud-risk scenario generator (defensive research only).")
app.add_typer(learn_app, name="learn")
console = Console()

_STATUS_STYLE = {Status.PASS: "green", Status.WARN: "yellow", Status.FAIL: "red"}


@app.command()
def generate(
    scenario: Annotated[Path, typer.Argument(help="Path to a scenario YAML file.")],
    out: Annotated[Path, typer.Option("--out", help="Output scenario directory.")],
    mutate_seed: Annotated[
        int | None,
        typer.Option("--mutate-seed", help="Emit a seeded, ground-truth-preserving variant."),
    ] = None,
) -> None:
    """Generate the full artifact tree for a scenario (optionally a seeded variant)."""
    try:
        spec = ScenarioSpec.model_validate(load_yaml(scenario))
        bundle = TemplateGenerator().generate(spec)
        bundle = _apply_mutation(bundle, spec, mutate_seed)
        # ``write_all`` runs the emitter, whose pre-emission collision guard raises a
        # ``GraphIntegrityError`` (a ``CloudforgeError``) — keep it inside the catch so
        # a colliding graph surfaces as a clean CLI error, not a raw traceback (FXL-N4).
        ScenarioArtifacts(ScenarioPaths.from_dir(out)).write_all(spec, bundle)
    except CloudforgeError as exc:
        console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    console.print(f"[green]generated[/green] scenario at {out}")


def _apply_mutation(
    bundle: ScenarioBundle, spec: ScenarioSpec, seed: int | None
) -> ScenarioBundle:
    """Return a seeded variant when ``--mutate-seed`` is set, else the bundle as-is."""
    if seed is None:
        return bundle
    return MutationGenerator(bundle, seed, spec.constraints.max_resources).generate()


@app.command()
def validate(
    scenario_dir: Annotated[Path, typer.Argument(help="A generated scenario directory.")],
) -> None:
    """Validate a generated scenario (fail-soft on missing optional tools)."""
    try:
        report = run_validations(scenario_dir)
    except CloudforgeError as exc:
        console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    for outcome in report.outcomes:
        console.print(outcome.render(), style=_STATUS_STYLE[outcome.status])
    if report.has_failure:
        raise typer.Exit(code=1)


@app.command()
def report(
    scenario_dir: Annotated[Path, typer.Argument(help="A generated scenario directory.")],
) -> None:
    """Render a human-readable report.md for a generated scenario."""
    try:
        written = ReportRenderer(scenario_dir).render_to_file()
    except CloudforgeError as exc:
        console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    console.print(f"[green]report written[/green] to {written}")


@app.command()
def version() -> None:
    """Print the cloudforge version."""
    console.print(__version__)
