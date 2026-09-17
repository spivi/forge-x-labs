"""The ``cloudforge`` Typer application: generate / validate / report.

Commands are thin — they load input, call the generate/validate/report modules, and
print results. All logic lives in the sub-packages so it stays reusable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError
from rich.console import Console

from app.cloudforge import __version__
from app.cloudforge.errors import CloudforgeError, UnknownEngineError
from app.cloudforge.generate.base import ScenarioBundle
from app.cloudforge.generate.composer import GraphComposer
from app.cloudforge.generate.mutation_generator import MutationGenerator
from app.cloudforge.generate.scaffold import ScaffoldError, new_family
from app.cloudforge.generate.template_generator import TemplateGenerator
from app.cloudforge.io.loaders import load_yaml
from app.cloudforge.io.paths import ScenarioPaths
from app.cloudforge.lab.cli import register_lab_commands
from app.cloudforge.learn.cli import learn_app
from app.cloudforge.models.scenario import ScenarioSpec
from app.cloudforge.pipeline.artifacts import ScenarioArtifacts
from app.cloudforge.report.renderer import ReportRenderer
from app.cloudforge.validate.orchestrator import run_validations
from app.cloudforge.validate.results import Status
from app.cloudforge.variation.cli import variation_app

app = typer.Typer(help="Local-first cloud-risk scenario generator (defensive research only).")
app.add_typer(learn_app, name="learn")
app.add_typer(variation_app, name="variation")
register_lab_commands(app)
console = Console()

_STATUS_STYLE = {Status.PASS: "green", Status.WARN: "yellow", Status.FAIL: "red"}

# Every command below loads/re-validates on-disk artifacts against Pydantic models and
# writes to a caller-supplied path. Besides ``CloudforgeError`` (our own domain errors),
# two more exception classes can escape from that: a hand-edited-but-well-formed YAML/JSON
# artifact that fails Pydantic schema validation raises ``pydantic.ValidationError`` (NOT a
# ``CloudforgeError``), and an unwritable/unreadable filesystem path raises ``OSError``
# (e.g. a read-only output directory). Both must surface as a clean ``error:`` + exit 1,
# never a raw traceback (stress-contract S1/S15) — mirrors the fail-soft pattern
# already used by ``report/renderer.py::_run_validation``.
_CLI_ERRORS: tuple[type[Exception], ...] = (CloudforgeError, ValidationError, OSError)
_SCAFFOLD_ERRORS: tuple[type[Exception], ...] = (ScaffoldError, OSError)


@app.command()
def generate(
    scenario: Annotated[Path, typer.Argument(help="Path to a scenario YAML file.")],
    out: Annotated[Path, typer.Option("--out", help="Output scenario directory.")],
    engine: Annotated[
        str,
        typer.Option("--engine", help="Generation engine: 'template' (default) or 'composer'."),
    ] = "template",
    seed: Annotated[
        int, typer.Option("--seed", help="Seed for the composer engine (deterministic).")
    ] = 0,
    mutate_seed: Annotated[
        int | None,
        typer.Option("--mutate-seed", help="Emit a seeded, ground-truth-preserving variant."),
    ] = None,
) -> None:
    """Generate the full artifact tree for a scenario (optionally a seeded variant)."""
    try:
        spec = ScenarioSpec.model_validate(load_yaml(scenario))
        bundle = _build_bundle(spec, engine, seed)
        bundle = _apply_mutation(bundle, spec, mutate_seed)
        # ``write_all`` runs the emitter, whose pre-emission collision guard raises a
        # ``GraphIntegrityError`` (a ``CloudforgeError``) — keep it inside the catch so
        # a colliding graph surfaces as a clean CLI error, not a raw traceback.
        ScenarioArtifacts(ScenarioPaths.from_dir(out)).write_all(spec, bundle)
    except _CLI_ERRORS as exc:
        console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    console.print(f"[green]generated[/green] scenario at {out}")


def _build_bundle(spec: ScenarioSpec, engine: str, seed: int) -> ScenarioBundle:
    """Dispatch to the requested engine; ``template`` (default) is unchanged."""
    if engine == "template":
        return TemplateGenerator().generate(spec)
    if engine == "composer":
        return GraphComposer(spec, seed).generate()
    raise UnknownEngineError(f"unknown engine {engine!r}; choose 'template' or 'composer'")


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
    except _CLI_ERRORS as exc:
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
    except _CLI_ERRORS as exc:
        console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    console.print(f"[green]report written[/green] to {written}")


@app.command()
def version() -> None:
    """Print the cloudforge version."""
    console.print(__version__)


@app.command("new-family")
def new_family_cmd(
    scenario_type: Annotated[str, typer.Argument(help="The new family's scenario_type.")],
    cloud: Annotated[str, typer.Option("--cloud", help="aws, azure, gcp, or k8s.")] = "aws",
    title: Annotated[
        str, typer.Option("--title", help="One-line teaching point for the family.")
    ] = "",
    root: Annotated[
        Path, typer.Option("--root", help="Repo root to write into (default: cwd).")
    ] = Path(),
) -> None:
    """Scaffold a new family: one core fragment module and one example spec."""
    try:
        fragment_path, example_path = new_family(scenario_type, cloud, title, root)
    except _SCAFFOLD_ERRORS as exc:
        console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    console.print(f"[green]wrote[/green] {fragment_path}")
    console.print(f"[green]wrote[/green] {example_path}")
    console.print(
        "\nNext steps:\n"
        f"  1. edit {fragment_path} with the family's real story\n"
        f"  2. run: cloudforge lab {example_path} --seed 17\n"
        "  3. run: PYTHONPATH=. pytest tests/cloudforge tests/unit tests/property -q"
    )
