"""Corpus-scale stage of the stress benchmark (issue #112).

Synthesizes ``RiskPattern`` corpora (``stress_benchmark_corpus_factory``) at 100 /
1,000 / 10,000 / 100,000 and measures dedup, quality-scoring, and export time + peak
memory — entirely in-memory (no disk writes; ``export.export_training`` is pure, only
``write_training_export`` touches disk and this benchmark never calls it, since the
point is to measure the learn-pipeline's own compute cost, not I/O).
"""

from __future__ import annotations

from app.cloudforge.learn import dedup as dedup_mod
from app.cloudforge.learn import export as export_mod
from app.cloudforge.learn import quality as quality_mod
from app.cloudforge.learn.pattern_models import RiskPattern
from scripts.stress_benchmark_corpus_factory import build_corpus
from scripts.stress_benchmark_util import Measurement, StageResult, measure, stage_result


def _score_all(patterns: list[RiskPattern]) -> list[RiskPattern]:
    return [quality_mod.score_pattern(p)[0] for p in patterns]


def run_corpus_scale(n: int) -> list[StageResult]:
    """Run the build/dedup/quality/export stages at corpus scale ``n``."""
    build: Measurement[list[RiskPattern]] = measure(lambda: build_corpus(n))
    patterns = build.result

    dedup_run: Measurement[tuple[list[RiskPattern], dedup_mod.DedupReport]] = measure(
        lambda: dedup_mod.dedup(patterns)
    )
    survivors, dedup_report = dedup_run.result

    quality_run: Measurement[list[RiskPattern]] = measure(lambda: _score_all(survivors))
    scored = quality_run.result

    summary_run: Measurement[quality_mod.CorpusSummary] = measure(
        lambda: quality_mod.summarize_corpus(scored, duplicates=len(patterns) - len(survivors))
    )

    export_run: Measurement[export_mod.TrainingExport] = measure(
        lambda: export_mod.export_training(scored)
    )

    return [
        stage_result("corpus_build", n, build),
        stage_result(
            "corpus_dedup",
            n,
            dedup_run,
            extra={"survivor_count": len(survivors), "dropped_count": n - len(survivors)},
        ),
        stage_result("corpus_quality_score", n, quality_run),
        stage_result(
            "corpus_summarize",
            n,
            summary_run,
            extra={"average_quality": summary_run.result.average_quality},
        ),
        stage_result(
            "corpus_export",
            n,
            export_run,
            extra={"exported_count": export_run.result.manifest.exported_count},
        ),
        StageResult(
            stage="corpus_dedup_report_groups",
            scale=n,
            elapsed_seconds=0.0,
            peak_memory_mib=0.0,
            per_item_ms=0.0,
            extra={"dedup_groups": len(dedup_report.groups)},
        ),
    ]


def run_all_corpus_scales(scales: list[int]) -> list[StageResult]:
    """Run every corpus-scale stage across ``scales``."""
    results: list[StageResult] = []
    for n in scales:
        results.extend(run_corpus_scale(n))
    return results
