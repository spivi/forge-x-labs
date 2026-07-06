"""The ``cloudforge learn`` Typer command group (design §10).

Wires the learning-corpus pipeline to the user as a nested ``learn`` sub-command
group on ``app.cloudforge.cli.app``: ``fetch-sources``, ``ingest --adapter <name>``,
``validate-corpus``, ``summarize``, ``export-training [--include-restricted]``. Every
command is thin — it loads input, calls exactly one ``learn/`` module, and prints with
``rich``, mirroring the top-level ``generate``/``validate``/``report`` commands.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from app.cloudforge import constants
from app.cloudforge.errors import CloudforgeError
from app.cloudforge.learn import export, fetch, quality, registry, validate
from app.cloudforge.learn._ingest import resolve_adapter, resolve_raw_path
from app.cloudforge.learn.corpus import load_corpus, save_corpus, validate_corpus
from app.cloudforge.learn.normalizer import PatternNormalizer
from app.cloudforge.learn.pattern_models import RiskPattern
from app.cloudforge.learn.summarize import render_summary_lines

learn_app = typer.Typer(help="Learning-corpus pipeline: fetch, ingest, validate, export.")
console = Console()


@learn_app.command("fetch-sources")
def fetch_sources(
    registry_path: Annotated[
        Path, typer.Option("--registry", help="Source registry YAML.")
    ] = Path(constants.SOURCE_REGISTRY_PATH),
    raw_dir: Annotated[Path, typer.Option("--raw-dir", help="Raw-cache output directory.")] = Path(
        constants.RAW_SOURCES_DIRNAME
    ),
) -> None:
    """Fetch every ``enabled`` registry source into ``data/raw/`` (hits the network)."""
    try:
        reg = registry.load_registry(registry_path)
        summary = fetch.fetch_all_sources(
            sources=registry.enabled_sources(reg), raw_dir=raw_dir, fetch_fn=None
        )
    except CloudforgeError as exc:
        console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    console.print(
        f"[green]fetched[/green] {summary.fetched}  "
        f"skipped {summary.skipped}  failed {summary.failed}"
    )


@learn_app.command("ingest")
def ingest(
    adapter: Annotated[str, typer.Option("--adapter", help="Adapter name to run.")],
    registry_path: Annotated[
        Path, typer.Option("--registry", help="Source registry YAML.")
    ] = Path(constants.SOURCE_REGISTRY_PATH),
    raw_dir: Annotated[
        Path, typer.Option("--raw-dir", help="Raw-cache directory to read from.")
    ] = Path(constants.RAW_SOURCES_DIRNAME),
    corpus_path: Annotated[
        Path, typer.Option("--corpus", help="Corpus JSONL to append to.")
    ] = Path(constants.CORPUS_JSONL_PATH),
) -> None:
    """Run ``adapter`` over its cached source(s), appending normalized patterns."""
    options = _IngestOptions(
        adapter_name=adapter, registry_path=registry_path, raw_dir=raw_dir, corpus_path=corpus_path
    )
    try:
        patterns = _run_ingest(options)
    except CloudforgeError as exc:
        console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    console.print(f"[green]ingested[/green] {len(patterns)} pattern(s) via {adapter!r}")


@dataclass(frozen=True, slots=True)
class _IngestOptions:
    """Bundles ``ingest``'s CLI options so the helper stays within the 3-param cap."""

    adapter_name: str
    registry_path: Path
    raw_dir: Path
    corpus_path: Path


def _run_ingest(options: _IngestOptions) -> list[RiskPattern]:
    """Extract + normalize every source using ``options.adapter_name``, appending to the corpus."""
    pattern_adapter = resolve_adapter(options.adapter_name)
    reg = registry.load_registry(options.registry_path)
    sources = [e for e in reg.sources if e.enabled and e.adapter == options.adapter_name]

    normalizer = PatternNormalizer()
    new_patterns = [
        normalizer.normalize(raw)
        for entry in sources
        for raw in pattern_adapter.extract(entry, resolve_raw_path(entry, options.raw_dir))
    ]

    existing = load_corpus(options.corpus_path) if options.corpus_path.exists() else []
    save_corpus([*existing, *new_patterns], options.corpus_path)
    return new_patterns


@learn_app.command("validate-corpus")
def validate_corpus_cmd(
    corpus_path: Annotated[
        Path, typer.Option("--corpus", help="Corpus JSONL to validate.")
    ] = Path(constants.CORPUS_JSONL_PATH),
) -> None:
    """Validate the corpus (fragments + corpus-level checks); exit 1 on FAIL.

    Persists each pattern's fragment-validation outcome (``validation_status``) back
    to the corpus, so downstream ``summarize``/``export-training`` read an
    already-validated corpus.
    """
    try:
        patterns = [validate.validate_fragment(p) for p in load_corpus(corpus_path)]
        save_corpus(patterns, corpus_path)
        report = validate_corpus(patterns)
    except CloudforgeError as exc:
        console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if report.passed:
        console.print(f"[green]PASS[/green] {report.pattern_count} pattern(s), no issues")
        return
    for issue in report.issues:
        console.print(f"[red]FAIL[/red] {issue.pattern_id}: {issue.check}: {issue.message}")
    raise typer.Exit(code=1)


@learn_app.command("summarize")
def summarize(
    corpus_path: Annotated[
        Path, typer.Option("--corpus", help="Corpus JSONL to summarize.")
    ] = Path(constants.CORPUS_JSONL_PATH),
) -> None:
    """Print coverage counts (provider/domain/family) plus quality distribution."""
    try:
        patterns = load_corpus(corpus_path)
        scored = [quality.score_pattern(p)[0] for p in patterns]
        summary = quality.summarize_corpus(scored)
    except CloudforgeError as exc:
        console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    for line in render_summary_lines(summary):
        console.print(line)


@learn_app.command("export-training")
def export_training_cmd(
    corpus_path: Annotated[
        Path, typer.Option("--corpus", help="Corpus JSONL to export from.")
    ] = Path(constants.CORPUS_JSONL_PATH),
    out_dir: Annotated[
        Path, typer.Option("--out", help="Training export output directory.")
    ] = Path(constants.TRAINING_EXPORT_DIRNAME),
    include_restricted: Annotated[
        bool,
        typer.Option("--include-restricted", help="Admit otherwise-eligible restricted patterns."),
    ] = False,
) -> None:
    """Apply the export gate and write the training bundle + manifest."""
    try:
        scored = [quality.score_pattern(p)[0] for p in load_corpus(corpus_path)]
        result = export.export_training(scored, include_restricted=include_restricted)
        export.write_training_export(result, out_dir)
    except CloudforgeError as exc:
        console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    console.print(
        f"[green]exported[/green] {result.manifest.exported_count}  "
        f"excluded {result.manifest.excluded_count}  -> {out_dir}"
    )
