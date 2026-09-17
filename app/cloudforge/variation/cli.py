"""The ``cloudforge variation`` Typer command group (design doc §8).

Wires the variation harness to the user as a nested ``variation`` sub-command group on
``app.cloudforge.cli.app``: ``run`` (compose+validate+report a suite → run tree),
``summarize`` (print a finished run's rollup + diversity), ``replay`` (determinism proof
for one scenario), and ``minimize-failure`` (shrink a captured failure). Every command is
thin — it loads input, calls exactly one ``variation/`` entry point, and prints with
``rich`` — mirroring the top-level ``generate``/``validate``/``report`` commands and the
``learn`` group. Handlers are wrapped in ``_CLI_ERRORS`` so bad input surfaces as a clean
``error:`` + exit 1, never a raw traceback (stress-contract S1/S15).
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError
from rich.console import Console

from app.cloudforge.errors import CloudforgeError
from app.cloudforge.io.loaders import dump_json, load_json, load_yaml
from app.cloudforge.io.paths import ScenarioPaths
from app.cloudforge.models.scenario import ScenarioSpec
from app.cloudforge.variation.gate import cosmetic_message, evaluate_gate
from app.cloudforge.variation.minimize import minimize
from app.cloudforge.variation.models import RunManifest, ScenarioManifestEntry, VariationSpec
from app.cloudforge.variation.replay import replay
from app.cloudforge.variation.suite_runner import run_suite

variation_app = typer.Typer(help="Variation harness: run suites, summarize, replay, minimize.")
console = Console()

# See ``app.cloudforge.cli._CLI_ERRORS``: our own ``CloudforgeError`` domain errors, plus a
# hand-edited-but-well-formed spec/manifest that fails Pydantic validation
# (``ValidationError``) and an unreadable/unwritable path (``OSError``) — all become a clean
# ``error:`` + exit 1, never a raw traceback.
_CLI_ERRORS: tuple[type[Exception], ...] = (CloudforgeError, ValidationError, OSError)


@variation_app.command("run")
def run(
    spec_path: Annotated[Path, typer.Argument(help="A VariationSpec YAML (e.g. aws_smoke.yaml).")],
    out: Annotated[Path, typer.Option("--out", help="The run directory to write the tree into.")],
    run_id: Annotated[
        str, typer.Option("--run-id", help="Run id label (a parameter, never generated).")
    ],
    gate: Annotated[
        bool,
        typer.Option("--gate", help="Fail the command if the diversity gate is not met."),
    ] = False,
) -> None:
    """Compose+validate+report every cell of the spec's sweep, writing the run tree
    directly under ``--out`` (so ``--out <dir>`` yields ``<dir>/manifest.json``). The
    ``--run-id`` is recorded as the manifest's run label. ``run_suite`` writes to
    ``parent/<name>``, so we pass ``out.parent`` + ``out.name`` and stamp ``run_id``."""
    try:
        spec = VariationSpec.model_validate(load_yaml(spec_path))
        result = run_suite(spec, out.parent, out.name)
        _relabel_run(out, run_id)
    except _CLI_ERRORS as exc:
        console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    fails = sum(1 for e in result.manifest.entries if e.validation_status == "fail")
    style = "yellow" if (fails or result.aborted) else "green"
    console.print(
        f"[{style}]run {run_id}[/{style}]: {len(result.manifest.entries)} scenarios, "
        f"{fails} failed, aborted={result.aborted} -> {out}"
    )
    if result.aborted:
        raise typer.Exit(code=1)
    if gate:
        try:
            _apply_gate(out)
        except _CLI_ERRORS as exc:
            console.print(f"[red]error:[/red] {exc}")
            raise typer.Exit(code=1) from exc


def _apply_gate(run_dir: Path) -> None:
    """Load the run's diversity report and exit 1 if the depth bar is missed."""
    report = load_json(run_dir / "diversity_report.json")
    result = evaluate_gate(report)
    for warning in result.warnings:
        console.print(f"[yellow]gate:[/yellow] {warning}")
    if result.passed:
        return
    for failure in result.failures:
        console.print(f"[red]gate:[/red] {failure}")
    console.print(f"[red]{cosmetic_message()}[/red]")
    raise typer.Exit(code=1)


def _relabel_run(run_dir: Path, run_id: str) -> None:
    """Stamp ``run_id`` as the manifest + summary run label (the on-disk dir name is
    ``--out``'s basename, which may differ from the caller's chosen ``--run-id``)."""
    manifest = load_json(run_dir / "manifest.json")
    manifest["run_id"] = run_id
    dump_json(run_dir / "manifest.json", manifest)
    summary = load_json(run_dir / "summary.json")
    summary["run_id"] = run_id
    dump_json(run_dir / "summary.json", summary)


@variation_app.command("summarize")
def summarize(
    run_dir: Annotated[
        Path, typer.Argument(help="A finished run directory (the --out passed to run).")
    ],
) -> None:
    """Print a finished run's summary rollup + diversity metrics."""
    try:
        summary = load_json(run_dir / "summary.json")
        diversity = load_json(run_dir / "diversity_report.json")
    except _CLI_ERRORS as exc:
        console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    console.print(
        f"[bold]run {summary.get('run_id')}[/bold]: {summary.get('total_scenarios')} scenarios, "
        f"{summary.get('failures')} failed, aborted={summary.get('aborted')}"
    )
    console.print(
        f"  unique graph shapes: {diversity.get('unique_graph_shapes')}  "
        f"decoys {diversity.get('pct_with_decoys')}%  "
        f"comp-controls {diversity.get('pct_with_compensating_controls')}%  "
        f"false-positives {diversity.get('pct_with_false_positives')}%"
    )
    if diversity.get("unsupported_axes"):
        console.print(f"  unsupported axes: {diversity['unsupported_axes']}", style="yellow")


@variation_app.command("replay")
def replay_command(
    run_dir: Annotated[Path, typer.Argument(help="A finished run directory.")],
    scenario_id: Annotated[str, typer.Option("--scenario-id", help="Scenario id to replay.")],
) -> None:
    """Prove one scenario's key artifacts are byte-reproducible (determinism check)."""
    try:
        matched = replay(run_dir, scenario_id)
    except _CLI_ERRORS as exc:
        console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    if matched:
        console.print(f"[green]replay ok[/green]: {scenario_id} is byte-reproducible")
        return
    console.print(f"[red]replay MISMATCH[/red]: {scenario_id} did not reproduce", style="red")
    raise typer.Exit(code=1)


@variation_app.command("minimize-failure")
def minimize_failure(
    run_dir: Annotated[Path, typer.Argument(help="A finished run directory.")],
    scenario_id: Annotated[
        str, typer.Option("--scenario-id", help="Failed scenario id to shrink.")
    ],
) -> None:
    """Shrink a captured failure to a smaller reproducer under failures/minimized/."""
    try:
        entry = _find_entry(run_dir, scenario_id)
        spec = _scenario_spec(run_dir / entry.artifact_dir)
        minimized = minimize(run_dir, scenario_id, spec, entry.seed)
    except _CLI_ERRORS as exc:
        console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    console.print(f"[green]minimized[/green] {scenario_id} -> {minimized}")


def _find_entry(run_dir: Path, scenario_id: str) -> ScenarioManifestEntry:
    manifest = RunManifest.model_validate(load_json(run_dir / "manifest.json"))
    for entry in manifest.entries:
        if entry.scenario_id == scenario_id:
            return entry
    raise CloudforgeError(f"no scenario {scenario_id!r} in {run_dir / 'manifest.json'}")


def _scenario_spec(scenario_dir: Path) -> ScenarioSpec:
    return ScenarioSpec.model_validate(
        load_yaml(ScenarioPaths.from_dir(scenario_dir).scenario_yaml)
    )
