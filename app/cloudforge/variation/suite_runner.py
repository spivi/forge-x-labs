"""The suite runner: composes, validates, and reports one scenario per
(family x scale x seed) cell of a ``VariationSpec``, then writes the §9 run tree.

``run_id`` is always a caller-supplied parameter — never generated here (no
wall-clock/PID/global RNG in this module); the only randomness anywhere in the
composed path is ``GraphComposer``'s ``Random(seed)``. All writes go through the
existing ``ScenarioPaths``/``ScenarioArtifacts`` primitives (§6: the harness adds
no new write primitive).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from app.cloudforge.generate.base import ScenarioBundle
from app.cloudforge.generate.composer import GraphComposer
from app.cloudforge.io.loaders import dump_json, dump_yaml
from app.cloudforge.io.paths import ScenarioPaths
from app.cloudforge.pipeline.artifacts import ScenarioArtifacts
from app.cloudforge.report.renderer import ReportRenderer
from app.cloudforge.validate.orchestrator import run_validations
from app.cloudforge.validate.results import Status
from app.cloudforge.variation.diversity import diversity_report
from app.cloudforge.variation.minimize import capture_failure
from app.cloudforge.variation.models import (
    RunManifest,
    ScenarioManifestEntry,
    ValidationStatus,
    VariationSpec,
)
from app.cloudforge.variation.spec_expander import ScenarioUnit, expand

_RUN_TREE_DIRS = ("failures/raw", "failures/minimized", "scenarios")


@dataclass
class RunSuiteResult:
    """Everything ``run_suite`` produces: the manifest plus whether it aborted."""

    manifest: RunManifest
    aborted: bool
    run_dir: Path
    bundles: list[tuple[str, ScenarioBundle]] = field(default_factory=list)


def run_suite(spec: VariationSpec, out_dir: Path | str, run_id: str) -> RunSuiteResult:
    """Compose+validate+report every cell of ``spec``'s sweep under
    ``out_dir/run_id``, honoring ``constraints.max_failures_before_abort``."""
    run_dir = _init_run_tree(Path(out_dir), run_id, spec)
    manifest = RunManifest(run_id=run_id)
    bundles: list[tuple[str, ScenarioBundle]] = []
    failures = 0
    aborted = False
    for unit in expand(spec):
        entry, bundle = _run_one(run_dir, unit)
        manifest.entries.append(entry)
        if bundle is not None:
            bundles.append((unit.family, bundle))
        if entry.validation_status == "fail":
            failures += 1
        if failures > spec.constraints.max_failures_before_abort:
            aborted = True
            break
    output = _RunOutput(
        manifest=manifest, bundles=bundles, aborted=aborted, axes=list(spec.variation_axes)
    )
    _finalize_run_tree(run_dir, output)
    return RunSuiteResult(manifest=manifest, aborted=aborted, run_dir=run_dir, bundles=bundles)


def _init_run_tree(out_dir: Path, run_id: str, spec: VariationSpec) -> Path:
    run_dir = out_dir / run_id
    for rel in _RUN_TREE_DIRS:
        (run_dir / rel).mkdir(parents=True, exist_ok=True)
    dump_yaml(run_dir / "variation_spec.yaml", spec.model_dump())
    return run_dir


def _run_one(
    run_dir: Path, unit: ScenarioUnit
) -> tuple[ScenarioManifestEntry, ScenarioBundle | None]:
    scenario_dir = run_dir / "scenarios" / unit.scenario_id
    started = time.monotonic()
    try:
        bundle = _compose_bundle(unit)
        ScenarioArtifacts(ScenarioPaths.from_dir(scenario_dir)).write_all(unit.spec, bundle)
        status, failure_id = _validate_and_report(run_dir, scenario_dir, unit)
    except Exception as exc:  # noqa: BLE001 - any composer/validator error is a captured FAIL
        failure_id = capture_failure(run_dir, unit.scenario_id, scenario_dir, exc)
        status = "fail"
        bundle = None
    duration = time.monotonic() - started
    rel_dir = scenario_dir.relative_to(run_dir)
    entry = _make_entry(unit, rel_dir, duration, status, failure_id)
    return entry, bundle


def _compose_bundle(unit: ScenarioUnit) -> ScenarioBundle:
    return GraphComposer(unit.spec, seed=unit.seed).generate()


def _validate_and_report(
    run_dir: Path, scenario_dir: Path, unit: ScenarioUnit
) -> tuple[ValidationStatus, str | None]:
    report = run_validations(scenario_dir)
    ReportRenderer(scenario_dir).render_to_file()
    if report.has_failure:
        fails = [o.render() for o in report.outcomes if o.status is Status.FAIL]
        failure_id = capture_failure(
            run_dir, unit.scenario_id, scenario_dir, AssertionError("; ".join(fails))
        )
        return "fail", failure_id
    return "pass", None


def _make_entry(
    unit: ScenarioUnit,
    rel_dir: Path,
    duration: float,
    status: ValidationStatus,
    failure_id: str | None,
) -> ScenarioManifestEntry:
    # ``artifact_dir`` is stored RELATIVE to the run dir (e.g. "scenarios/<id>") so the
    # manifest is portable and byte-identical across run locations — determinism is a
    # property of the content, not the absolute output path. Consumers (replay) resolve
    # it against the run dir.
    return ScenarioManifestEntry(
        scenario_id=unit.scenario_id,
        family=unit.family,
        seed=unit.seed,
        scale=unit.scale,
        axes=unit.spec.variation_axes,
        artifact_dir=rel_dir.as_posix(),
        gen_duration_sec=duration,
        validation_status=status,
        scanner_status="not_scored",
        failure_id=failure_id,
    )


@dataclass
class _RunOutput:
    """The finalize inputs, grouped so ``_finalize_run_tree`` stays within the
    param limit and the diversity report is computed over the run's real axes."""

    manifest: RunManifest
    bundles: list[tuple[str, ScenarioBundle]]
    aborted: bool
    axes: list[str]


def _finalize_run_tree(run_dir: Path, output: _RunOutput) -> None:
    dump_json(run_dir / "manifest.json", output.manifest.model_dump())
    dump_json(
        run_dir / "diversity_report.json",
        diversity_report(output.bundles, output.axes),
    )
    dump_json(run_dir / "summary.json", _summary(output.manifest, output.aborted))


def _summary(manifest: RunManifest, aborted: bool) -> dict[str, object]:
    fails = sum(1 for e in manifest.entries if e.validation_status == "fail")
    return {
        "run_id": manifest.run_id,
        "total_scenarios": len(manifest.entries),
        "failures": fails,
        "aborted": aborted,
    }


__all__ = ["RunSuiteResult", "run_suite"]
