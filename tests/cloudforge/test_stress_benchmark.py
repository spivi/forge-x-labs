"""Opt-in wrapper for the FXL-112 / FXL-STRESS-10 scale benchmark.

Marked ``stress`` + ``slow`` (mirrors ``test_mutation_stress.py``, FXL-N3): deselected
from the default ``pytest`` run and the pre-push backstop; opt in with
``pytest -m stress``. This is a MEASUREMENT wrapper, not a perf gate — the ticket is
explicit that this suite measures scaling to catch accidental O(N^2), it does not
assert a hard time/memory bound. Assertions here only check the benchmark itself
completed and produced sane structural output (non-negative timings, expected stage
coverage), never a "must be faster than X" gate.

The full 10,000/100,000-scale sweep is the ``scripts/stress_benchmark.py`` CLI
entrypoint, run manually or in a scheduled job — not from this test, to keep
``pytest -m stress`` itself bounded. Set ``CLOUDFORGE_STRESS_BENCH_FULL=1`` to run
the full default scales here instead of the reduced smoke scales.
"""

from __future__ import annotations

import os

import pytest

from scripts.stress_benchmark_corpus import run_all_corpus_scales
from scripts.stress_benchmark_scenario import run_all_scenario_scales
from scripts.stress_benchmark_util import StageResult

pytestmark = [pytest.mark.stress, pytest.mark.slow]

_FULL_ENV = "CLOUDFORGE_STRESS_BENCH_FULL"
_SMOKE_SCENARIO_SCALES = [10, 100]
_SMOKE_CORPUS_SCALES = [10, 100, 1_000]
_FULL_SCENARIO_SCALES = [100, 1_000, 10_000]
_FULL_CORPUS_SCALES = [100, 1_000, 10_000, 100_000]


def _scenario_scales() -> list[int]:
    return _FULL_SCENARIO_SCALES if os.environ.get(_FULL_ENV) == "1" else _SMOKE_SCENARIO_SCALES


def _corpus_scales() -> list[int]:
    return _FULL_CORPUS_SCALES if os.environ.get(_FULL_ENV) == "1" else _SMOKE_CORPUS_SCALES


def _assert_sane(results: list[StageResult], scales: list[int]) -> None:
    assert results, "benchmark produced no stage results"
    for r in results:
        assert r.elapsed_seconds >= 0.0
        assert r.peak_memory_mib >= 0.0
        assert r.scale in scales


def test_scenario_scale_benchmark_runs() -> None:
    """The scenario-scale stage runs at every configured scale without raising."""
    scales = _scenario_scales()
    results = run_all_scenario_scales(scales)
    _assert_sane(results, scales)
    stages = {r.stage for r in results}
    assert {"scenario_generate", "scenario_validate", "scenario_report"} <= stages


def test_corpus_scale_benchmark_runs() -> None:
    """The corpus-scale stage runs at every configured scale without raising."""
    scales = _corpus_scales()
    results = run_all_corpus_scales(scales)
    _assert_sane(results, scales)
    stages = {r.stage for r in results}
    assert {"corpus_dedup", "corpus_quality_score", "corpus_export"} <= stages
