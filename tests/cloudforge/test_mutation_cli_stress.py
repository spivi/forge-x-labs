"""CLI-level mutation determinism + risk-preservation stress runner (FXL-STRESS-4,
issue #114).

Contract clauses under test (``docs/testing/stress-contract.md``):
  * S10 — same input AND seed produce byte-identical output. Checked by invoking
    the REAL ``cloudforge generate --mutate-seed N`` CLI command TWICE per seed and
    diffing the on-disk ``graph.json`` / ``expected_findings.json`` /
    ``ground_truth_paths.json`` bytes.
  * S11 — different seeds preserve risk invariants (critical path, expected
    findings, no forbidden permission) while still producing cosmetic diversity.
    Checked via the real ``validate`` CLI command (exit 0) AND the real ``report``
    CLI command's own ``## Validation`` section (the wave-1 fix — a report must
    never claim success for a scenario that FAILed validation, so reading the
    report's verdict is the S15-honoring way to assert S11 here).

This complements (does not replace) the existing FXL-N3 suite
(``test_mutation_stress.py``): FXL-N3 is single-family, in-memory, 100 seeds,
graph-risk-engine-only. This module is BOTH families, drives the actual CLI
end-to-end (generate x2/validate/report on disk), and covers the full 0..999
seed range behind ``-m stress`` per the ticket's acceptance criteria.

Fast suite: a 25-seed subset per family (unmarked, runs in the default `pytest`
invocation). Full: 1,000 seeds x 2 families = 2,000 variants, `-m stress` only
(each variant does two subprocess-free CLI invocations + a validate + a report,
so the full run is intentionally NOT part of the default/pre-push profile).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.cloudforge.cli_mutation_stress_support import (
    FAMILIES,
    CliSeedResult,
    MutationSummary,
    aggregate,
    run_cli_seed,
)

# Fast-suite subset: 25 seeds, deterministic selection (not random), unmarked so it
# runs in the default `pytest tests/cloudforge/ -q --no-cov` invocation.
_FAST_SEEDS = range(0, 25)

# Full stress range required by issue #114's acceptance criteria.
_FULL_SEEDS = range(0, 1000)

_DATA_DIR = Path(__file__).parent / "data"
_SAMPLE_SUMMARY = _DATA_DIR / "mutation_cli_summary.sample.json"


def _run_all(seeds: range, tmp_root: Path) -> list[CliSeedResult]:
    return [run_cli_seed(family, seed, tmp_root) for family in FAMILIES for seed in seeds]


def _assert_clean(summary: MutationSummary, seeds: range) -> None:
    total = len(FAMILIES) * len(seeds)
    assert summary.total_variants == total
    assert not summary.nondeterminism_failures, (
        "S10 VIOLATION(s) — nondeterministic mutation output:\n"
        + "\n".join(summary.nondeterminism_failures)
    )
    assert not summary.validation_failures, (
        "S11 VIOLATION(s) — risk not preserved / validation failed:\n"
        + "\n".join(summary.validation_failures)
    )
    assert not summary.forbidden_perm_failures, (
        "S11 VIOLATION(s) — forbidden permission introduced by mutation:\n"
        + "\n".join(summary.forbidden_perm_failures)
    )
    assert summary.deterministic == total
    assert summary.validated == total
    assert summary.path_preserved == total
    assert summary.forbidden_perm_hits == 0
    for family in FAMILIES:
        assert summary.per_family_distinct_cosmetic_variants[family] > 0, (
            f"{family}: zero cosmetic diversity across {len(seeds)} seeds"
        )


def test_mutation_cli_fast_subset(tmp_path: Path) -> None:
    """25-seed x 2-family fast-suite subset: determinism + risk preservation."""
    results = _run_all(_FAST_SEEDS, tmp_path)
    summary = aggregate(results, _FAST_SEEDS)
    live = summary.write(tmp_path / "mutation_summary.json")

    _assert_clean(summary, _FAST_SEEDS)

    reloaded = json.loads(live.read_text())
    assert reloaded["total_variants"] == summary.total_variants


@pytest.mark.stress
@pytest.mark.slow
def test_mutation_cli_full_1000_seeds(tmp_path: Path) -> None:
    """Full 2 families x 1,000 seeds = 2,000 variants (issue #114 acceptance).

    Deselected by default (``addopts = -m 'not stress and not internet'``); run
    explicitly with ``pytest -m stress``. Writes the aggregate to
    ``mutation_summary.json`` (tmp) and refreshes the committed reviewable sample.
    """
    results = _run_all(_FULL_SEEDS, tmp_path)
    summary = aggregate(results, _FULL_SEEDS)
    live = summary.write(tmp_path / "mutation_summary.json")
    summary.write(_SAMPLE_SUMMARY)

    _assert_clean(summary, _FULL_SEEDS)

    reloaded = json.loads(live.read_text())
    assert reloaded["total_variants"] == 2000
