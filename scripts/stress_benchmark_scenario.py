"""Scenario-scale stage of the stress benchmark (issue #112).

Generates N scenarios via seeded mutation of a real base bundle (same approach as
the mutation stress suite), writes each to a single reused on-disk scenario
directory (bounded — never more than one scenario tree on disk at a time), runs the
stdlib-only ``run_local_validations`` (per the ticket note: NOT the full
CLI-validate, which shells out to terraform/checkov/opa — STRESS-4/S15 learning),
and renders the Markdown report. Measures time + peak memory for generate,
validate, and report separately, plus output tree size for one sample.

Writing 10,000 full scenario trees to disk simultaneously would risk the STRESS-3
disk-full failure mode; reusing one bounded directory keeps disk usage constant
regardless of scale.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import yaml

from app.cloudforge.generate.base import ScenarioBundle
from app.cloudforge.generate.mutation_generator import MutationGenerator
from app.cloudforge.generate.template_generator import TemplateGenerator
from app.cloudforge.io.paths import ScenarioPaths
from app.cloudforge.models.scenario import ScenarioSpec
from app.cloudforge.pipeline.artifacts import ScenarioArtifacts
from app.cloudforge.report.renderer import ReportRenderer
from app.cloudforge.validate.orchestrator import run_local_validations
from scripts.stress_benchmark_util import Measurement, StageResult, measure, stage_result

_BASE_SPEC_PATH = Path("examples/ci_cd_iam_chain.yaml")


def _load_base() -> tuple[ScenarioSpec, ScenarioBundle]:
    spec = ScenarioSpec.model_validate(yaml.safe_load(_BASE_SPEC_PATH.read_text()))
    bundle = TemplateGenerator().generate(spec)
    return spec, bundle


def _generate_n(base: ScenarioBundle, spec: ScenarioSpec, n: int) -> list[ScenarioBundle]:
    """Mutate ``n`` seeded variants of ``base`` (mirrors the mutation stress suite's
    approach to volume)."""
    max_resources = spec.constraints.max_resources
    return [MutationGenerator(base, seed, max_resources).generate() for seed in range(n)]


def _write_and_validate_all(
    bundles: list[ScenarioBundle], spec: ScenarioSpec, scenario_dir: Path
) -> int:
    """Write + local-validate every bundle into ONE reused directory (bounded disk).

    Returns the count of bundles whose validation produced no FAIL outcome (a
    sanity signal, not a hard gate — this ticket measures, it does not assert).
    """
    paths = ScenarioPaths.from_dir(scenario_dir)
    clean = 0
    for bundle in bundles:
        if scenario_dir.exists():
            shutil.rmtree(scenario_dir)
        ScenarioArtifacts(paths).write_all(spec, bundle)
        report = run_local_validations(scenario_dir)
        if not report.has_failure:
            clean += 1
    return clean


def _report_all(n: int, spec: ScenarioSpec, scenario_dir: Path) -> int:
    """Render the Markdown report for the same reused directory ``n`` times."""
    total_len = 0
    for _ in range(n):
        total_len += len(ReportRenderer(scenario_dir).render())
    return total_len


def _sample_tree_bytes(bundle: ScenarioBundle, spec: ScenarioSpec, tmp_root: Path) -> int:
    """One-off: on-disk byte size of a single scenario's full output tree."""
    sample_dir = tmp_root / "sample"
    ScenarioArtifacts(ScenarioPaths.from_dir(sample_dir)).write_all(spec, bundle)
    total = sum(f.stat().st_size for f in sample_dir.rglob("*") if f.is_file())
    shutil.rmtree(sample_dir)
    return total


def run_scenario_scale(n: int, tmp_root: Path) -> list[StageResult]:
    """Run the generate/validate/report stages at scale ``n``; return their results."""
    spec, base = _load_base()
    scenario_dir = tmp_root / "scenario_bench"

    gen: Measurement[list[ScenarioBundle]] = measure(lambda: _generate_n(base, spec, n))
    bundles = gen.result

    sample_bytes = _sample_tree_bytes(bundles[0], spec, tmp_root)

    val: Measurement[int] = measure(lambda: _write_and_validate_all(bundles, spec, scenario_dir))

    rep: Measurement[int] = measure(lambda: _report_all(n, spec, scenario_dir))

    if scenario_dir.exists():
        shutil.rmtree(scenario_dir)

    return [
        stage_result("scenario_generate", n, gen),
        stage_result(
            "scenario_validate",
            n,
            val,
            extra={"clean_count": val.result, "sample_tree_bytes": sample_bytes},
        ),
        stage_result("scenario_report", n, rep, extra={"total_report_chars": rep.result}),
    ]


def run_all_scenario_scales(scales: list[int]) -> list[StageResult]:
    """Run every scenario-scale stage across ``scales`` inside one bounded tmp dir."""
    results: list[StageResult] = []
    with tempfile.TemporaryDirectory(prefix="cloudforge_stress_bench_") as tmp:
        for n in scales:
            results.extend(run_scenario_scale(n, Path(tmp)))
    return results
