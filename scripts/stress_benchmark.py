#!/usr/bin/env python
"""FXL-112 / FXL-STRESS-10 — scenario + corpus scale benchmark (measure, don't optimize).

Opt-in only: run directly with the venv interpreter, NEVER imported by the fast
suite. Two modes:

  * scenario scale — generate + local-validate + report at 100 / 1,000 / 10,000
    scenarios (seeded mutation for volume, one reused bounded tmp dir on disk).
  * corpus scale — dedup + quality-score + export synthetic ``RiskPattern`` corpora
    at 100 / 1,000 / 10,000 / 100,000 (in-memory only).

Emits ``benchmark_results.json`` (default: repo root) with every stage's elapsed
time, peak memory, and a per-scale-step scaling ratio so accidental O(N^2) shows up
as a ratio well above 1.0 rather than requiring a human to eyeball raw seconds.

Usage:
    PYTHONPATH=. .venv/bin/python scripts/stress_benchmark.py
    PYTHONPATH=. .venv/bin/python scripts/stress_benchmark.py --corpus-max 10000
    PYTHONPATH=. .venv/bin/python scripts/stress_benchmark.py --out /tmp/bench.json

This is a measurement tool, not a test: there is no pass/fail exit code tied to
performance. It exits non-zero only if a stage raises.

A reviewable full-scale sample run is committed at
``tests/cloudforge/data/benchmark_results.sample.json``.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path

from scripts.stress_benchmark_corpus import run_all_corpus_scales
from scripts.stress_benchmark_scenario import run_all_scenario_scales
from scripts.stress_benchmark_util import StageResult, scaling_ratio

_DEFAULT_SCENARIO_SCALES = [100, 1_000, 10_000]
_DEFAULT_CORPUS_SCALES = [100, 1_000, 10_000, 100_000]
_SUPERLINEAR_RATIO_THRESHOLD = 2.0


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scenario-max",
        type=int,
        default=max(_DEFAULT_SCENARIO_SCALES),
        help="largest scenario-scale N to run (runs every default scale <= this)",
    )
    parser.add_argument(
        "--corpus-max",
        type=int,
        default=max(_DEFAULT_CORPUS_SCALES),
        help="largest corpus-scale N to run (runs every default scale <= this)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("benchmark_results.json"),
        help="where to write the JSON results",
    )
    return parser.parse_args(argv)


def _scales_up_to(defaults: list[int], maximum: int) -> list[int]:
    return [n for n in defaults if n <= maximum]


def _flag_scaling_concerns(results: list[StageResult]) -> list[str]:
    """Compare consecutive same-stage scales; flag a ratio above the threshold."""
    by_stage: dict[str, list[StageResult]] = {}
    for r in results:
        by_stage.setdefault(r.stage, []).append(r)

    concerns: list[str] = []
    for stage, stage_results in by_stage.items():
        ordered = sorted(stage_results, key=lambda r: r.scale)
        for prev, curr in zip(ordered, ordered[1:], strict=False):
            ratio = scaling_ratio(prev, curr)
            if ratio is not None and ratio > _SUPERLINEAR_RATIO_THRESHOLD:
                concerns.append(
                    f"{stage}: scale {prev.scale}->{curr.scale} time ratio "
                    f"{ratio:.2f}x the scale ratio (super-linear candidate; "
                    f"{prev.elapsed_seconds:.4f}s -> {curr.elapsed_seconds:.4f}s)"
                )
    return concerns


def _flag_memory_concerns(results: list[StageResult]) -> list[str]:
    """Flag any stage whose peak memory per item grows sharply with scale."""
    by_stage: dict[str, list[StageResult]] = {}
    for r in results:
        by_stage.setdefault(r.stage, []).append(r)

    concerns: list[str] = []
    for stage, stage_results in by_stage.items():
        ordered = sorted(stage_results, key=lambda r: r.scale)
        per_item = [(r.scale, r.peak_memory_mib / r.scale if r.scale else 0.0) for r in ordered]
        for (prev_scale, prev_mib), (curr_scale, curr_mib) in zip(
            per_item, per_item[1:], strict=False
        ):
            if prev_mib > 0 and curr_mib / prev_mib > _SUPERLINEAR_RATIO_THRESHOLD:
                concerns.append(
                    f"{stage}: per-item peak memory grew {curr_mib / prev_mib:.2f}x from "
                    f"scale {prev_scale} to {curr_scale} ({prev_mib:.5f} -> "
                    f"{curr_mib:.5f} MiB/item; possible unbounded growth)"
                )
    return concerns


def _build_report(
    scenario_results: list[StageResult], corpus_results: list[StageResult]
) -> dict[str, object]:
    all_results = scenario_results + corpus_results
    return {
        "ticket": "FXL-112 / FXL-STRESS-10",
        "purpose": "measure scaling, not optimize",
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "scenario_scale": [r.to_dict() for r in scenario_results],
        "corpus_scale": [r.to_dict() for r in corpus_results],
        "scaling_concerns": _flag_scaling_concerns(all_results),
        "memory_concerns": _flag_memory_concerns(all_results),
    }


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)

    scenario_scales = _scales_up_to(_DEFAULT_SCENARIO_SCALES, args.scenario_max)
    corpus_scales = _scales_up_to(_DEFAULT_CORPUS_SCALES, args.corpus_max)

    print(f"scenario scales: {scenario_scales}", file=sys.stderr)
    scenario_results = run_all_scenario_scales(scenario_scales)

    print(f"corpus scales: {corpus_scales}", file=sys.stderr)
    corpus_results = run_all_corpus_scales(corpus_scales)

    report = _build_report(scenario_results, corpus_results)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"wrote {args.out}", file=sys.stderr)

    for concern in report["scaling_concerns"] + report["memory_concerns"]:  # type: ignore[operator]
        print(f"CONCERN: {concern}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
