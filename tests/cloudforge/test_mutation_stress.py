"""Mutation stress suite — statistical, not anecdotal, risk preservation.

Strengthens gap #12 of the 12-point validated definition: proves the
seeded ``MutationGenerator`` preserves the intended risk across MANY seeds, not just
a handful. Every test here is marked ``stress`` and is DESELECTED from the default
``pytest`` run (``addopts = -m 'not stress'``). Run explicitly with::

    pytest -m stress

Per-seed assertions (over the whole range):
  * same seed -> byte-identical graph; different seed -> different cosmetic variants,
    but the ground-truth NODE IDs on the critical path are UNCHANGED;
  * the required critical ground-truth path still exists (nodes + edges present,
    reachable) — checked by the real graph-risk engine;
  * severity mix preserved (multiset of finding severities) and expected findings
    preserved (same finding ids AND families);
  * NO new forbidden permission introduced (graph-risk ``check_forbidden_permissions``);
  * ``terraform validate`` still passes on a bounded SAMPLE of seeds (real terraform
    init downloads a ~650 MB provider and costs ~seconds/seed, so running it on all
    100 would be ~35 min + tens of GB — we sample and log exactly what we sampled).

The aggregate is written to ``mutation_summary.json`` next to a committed sample
(``tests/cloudforge/data/mutation_summary.sample.json``) so the numbers are reviewable.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from app.cloudforge.generate.base import ScenarioBundle
from app.cloudforge.generate.template_generator import TemplateGenerator
from app.cloudforge.models.scenario import ScenarioSpec
from app.cloudforge.validate.results import Status
from tests.cloudforge.mutation_stress_support import (
    STRESS_1K_ENV,
    MutationStressSummary,
    aggregate,
    critical_path_node_ids,
    run_seed,
    terraform_available,
    terraform_validate_variant,
)

# Marked BOTH `stress` (so the default `pytest`/CI run deselects via addopts
# `-m 'not stress'`) and `slow` (so the pre-push backstop `-m 'not slow'` also skips
# them, keeping `git push` fast). `pytest -m stress` still opts back in explicitly.
pytestmark = [pytest.mark.stress, pytest.mark.slow]

# 100-seed local range; the graph-risk pass runs on every seed here.
_LOCAL_SEEDS = range(1, 101)
# Every 10th seed is sampled for REAL terraform validate (10 of the 100) — bounds
# wall-clock + disk while still exercising the compiled Terraform for variants.
_TERRAFORM_SAMPLE_EVERY = 10
# The opt-in variant: 1,000 seeds, graph-risk-only (no terraform), env-gated.
_STRESS_1K_SEEDS = range(1, 1001)

# Committed sample of the aggregate for reviewers; the live run writes a fresh copy.
_DATA_DIR = Path(__file__).parent / "data"
_SAMPLE_SUMMARY = _DATA_DIR / "mutation_summary.sample.json"


def _base(spec: ScenarioSpec) -> ScenarioBundle:
    return TemplateGenerator().generate(spec)


def _sampled_terraform_seeds(seeds: range) -> list[int]:
    return [s for s in seeds if s % _TERRAFORM_SAMPLE_EVERY == 0]


def _run_terraform_sample(
    base: ScenarioBundle,
    spec: ScenarioSpec,
    summary: MutationStressSummary,
    tmp_path: Path,
) -> None:
    """Run real terraform validate on the sampled seeds; record what was sampled."""
    sampled = _sampled_terraform_seeds(_LOCAL_SEEDS)
    if not terraform_available():
        summary.terraform_sampling_note = (
            f"terraform not installed — {len(sampled)} seeds would have been sampled "
            f"(every {_TERRAFORM_SAMPLE_EVERY}th of {len(_LOCAL_SEEDS)}); graph-risk ran on all"
        )
        return
    plugin_cache = tmp_path / "tf_plugin_cache"
    summary.terraform_sampled_seeds = sampled
    summary.terraform_sampling_note = (
        f"real `terraform validate` sampled on {len(sampled)} of {len(_LOCAL_SEEDS)} seeds "
        f"(every {_TERRAFORM_SAMPLE_EVERY}th); graph-risk (incl. forbidden-permission + "
        f"path-reachability) ran on ALL {len(_LOCAL_SEEDS)} seeds. Provider shared via one "
        f"TF_PLUGIN_CACHE_DIR so disk stays bounded."
    )
    for seed in sampled:
        status = terraform_validate_variant(
            base, spec, seed, tmp_path / f"tf_variant_{seed:04d}", plugin_cache
        )
        # PASS = validated. WARN = environmental (network/provider) — fail-soft, not a
        # risk-preservation defect. FAIL = a real terraform config error (a defect).
        if status is Status.PASS:
            summary.terraform_sampled_valid += 1
        elif status is Status.FAIL:
            summary.failures.append(f"seed {seed}: terraform validate FAILED")


def _write_summaries(summary: MutationStressSummary, tmp_path: Path) -> Path:
    """Write the live aggregate to tmp AND refresh the committed sample."""
    live = summary.write(tmp_path / "mutation_summary.json")
    summary.write(_SAMPLE_SUMMARY)
    return live


def test_mutation_stress_100_seeds(example_spec: ScenarioSpec, tmp_path: Path) -> None:
    """100-seed risk-preservation sweep + sampled terraform validate + aggregate."""
    base = _base(example_spec)
    results = [run_seed(base, example_spec, seed) for seed in _LOCAL_SEEDS]
    summary = aggregate(base, results)
    _run_terraform_sample(base, example_spec, summary, tmp_path)
    live = _write_summaries(summary, tmp_path)

    total = len(_LOCAL_SEEDS)
    # Prominent, itemized defect report if ANYTHING failed risk preservation.
    assert not summary.failures, (
        "mutation risk-preservation DEFECT(s) across seeds:\n" + "\n".join(summary.failures)
    )
    assert summary.seeds_run == total
    assert summary.path_preserved == total, "some seed dropped the critical path"
    assert summary.no_forbidden_permission == total, "some seed introduced a forbidden perm"
    assert summary.validated_variants == total, "some variant did not fully validate"
    assert summary.severity_mix_preserved == total, "severity mix changed under mutation"
    assert summary.findings_preserved == total, "finding ids changed under mutation"
    assert summary.families_preserved == total, "finding families changed under mutation"
    # Every terraform-sampled variant that actually ran must be valid (PASS or WARN,
    # never FAIL — a FAIL would already be in summary.failures above).
    assert summary.terraform_sampled_valid == len(summary.terraform_sampled_seeds) or (
        not terraform_available()
    )
    # Sanity: the live aggregate is real JSON and mirrors the object we asserted on.
    reloaded = json.loads(live.read_text())
    assert reloaded["seeds_run"] == total


def test_same_seed_byte_identical_over_range(example_spec: ScenarioSpec) -> None:
    """Determinism at scale: re-running any seed yields a byte-identical graph."""
    base = _base(example_spec)
    for seed in _LOCAL_SEEDS:
        first = run_seed(base, example_spec, seed)
        second = run_seed(base, example_spec, seed)
        assert first.graph_hash == second.graph_hash, f"seed {seed} not deterministic"


def test_distinct_seeds_produce_distinct_variants(example_spec: ScenarioSpec) -> None:
    """Different seeds must yield different cosmetic variants (diversity)."""
    base = _base(example_spec)
    hashes = {run_seed(base, example_spec, seed).graph_hash for seed in _LOCAL_SEEDS}
    # The mutation space (names x tags x extra-subnet cidr) easily exceeds 100 draws;
    # require broad — not necessarily perfect — diversity to stay robust to collisions.
    assert len(hashes) >= int(0.9 * len(_LOCAL_SEEDS)), (
        f"only {len(hashes)} distinct variants across {len(_LOCAL_SEEDS)} seeds"
    )


def test_critical_path_node_ids_invariant_over_range(example_spec: ScenarioSpec) -> None:
    """The ground-truth critical-path NODE IDS never change, whatever the seed."""
    base = _base(example_spec)
    expected = critical_path_node_ids(base)
    assert expected, "fixture has no critical path — cannot assert invariance"
    for seed in _LOCAL_SEEDS:
        assert run_seed(base, example_spec, seed).critical_path_node_ids == expected


@pytest.mark.skipif(
    os.environ.get(STRESS_1K_ENV) != "1",
    reason=f"opt-in 1,000-seed variant — set {STRESS_1K_ENV}=1 to run (graph-risk only)",
)
def test_mutation_stress_1000_seeds_opt_in(example_spec: ScenarioSpec, tmp_path: Path) -> None:
    """Opt-in 1,000-seed, graph-risk-only sweep (no terraform). Env-gated; not in CI."""
    base = _base(example_spec)
    results = [run_seed(base, example_spec, seed) for seed in _STRESS_1K_SEEDS]
    summary = aggregate(base, results)
    summary.terraform_sampling_note = "1,000-seed variant: graph-risk only, terraform not run"
    summary.write(tmp_path / "mutation_summary_1000.json")

    total = len(_STRESS_1K_SEEDS)
    assert not summary.failures, "1,000-seed mutation DEFECT(s):\n" + "\n".join(summary.failures)
    assert summary.path_preserved == total
    assert summary.no_forbidden_permission == total
    assert summary.validated_variants == total
    assert summary.severity_mix_preserved == total
    assert summary.findings_preserved == total
