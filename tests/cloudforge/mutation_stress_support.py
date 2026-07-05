"""Support helpers for the mutation stress suite (FXL-N3).

Pure, importable helpers so the stress test itself stays declarative:

  * ``run_seed`` — mutate the base bundle for one seed and collect the per-seed
    risk-preservation evidence (graph-risk outcomes, node ids, byte hash).
  * ``MutationStressSummary`` — the aggregate that becomes ``mutation_summary.json``.
  * ``terraform_validate_variant`` — emit + ``terraform validate`` a single variant,
    sharing one provider plugin cache so 100 seeds don't blow up disk/network.

These live under ``tests/`` (not ``app/``) because they exist only to *measure*
the shipped mutation engine — they intentionally add no product behaviour and never
touch the mutation/emitter/scorer logic under test.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

from app.cloudforge.generate.base import ScenarioBundle
from app.cloudforge.generate.mutation_generator import MutationGenerator
from app.cloudforge.io.paths import ScenarioPaths
from app.cloudforge.models.findings import FindingFamily
from app.cloudforge.models.scenario import ScenarioSpec
from app.cloudforge.pipeline.artifacts import ScenarioArtifacts
from app.cloudforge.validate import external_scans, tool_probe
from app.cloudforge.validate.graph_risk import GraphRiskEngine
from app.cloudforge.validate.results import Status

# The two graph-risk checks whose PASS is the crux of "mutation is risk-preserving".
PATH_PRESERVED_LABEL = "ground-truth path exists"
NO_FORBIDDEN_LABEL = "no forbidden permissions"

# Opt-in gate for the 1,000-seed variant: only runs when this env var is set.
STRESS_1K_ENV = "CLOUDFORGE_STRESS_1K"


def _graph_bytes(bundle: ScenarioBundle) -> bytes:
    """Canonical byte serialization of a variant's graph (matches artifact JSON)."""
    return json.dumps(bundle.graph.model_dump(by_alias=True), indent=2, sort_keys=False).encode()


def _graph_hash(bundle: ScenarioBundle) -> str:
    return hashlib.sha256(_graph_bytes(bundle)).hexdigest()


def critical_path_node_ids(bundle: ScenarioBundle) -> tuple[str, ...]:
    """Ground-truth node ids on every critical path, in author order."""
    ids: list[str] = []
    for path in bundle.ground_truth.paths:
        if path.severity == "critical":
            ids.extend(path.nodes)
    return tuple(ids)


def severity_multiset(bundle: ScenarioBundle) -> tuple[str, ...]:
    """The sorted multiset of expected-finding severities (mix, not just the set)."""
    return tuple(sorted(f.severity for f in bundle.findings.findings))


def finding_ids(bundle: ScenarioBundle) -> frozenset[str]:
    return frozenset(f.id for f in bundle.findings.findings)


def finding_families(bundle: ScenarioBundle) -> frozenset[FindingFamily]:
    return frozenset(f.family for f in bundle.findings.findings)


@dataclass(frozen=True)
class SeedResult:
    """Per-seed risk-preservation evidence for one mutated variant."""

    seed: int
    graph_hash: str
    node_ids: frozenset[str]
    critical_path_node_ids: tuple[str, ...]
    severity_multiset: tuple[str, ...]
    finding_ids: frozenset[str]
    finding_families: frozenset[FindingFamily]
    risk_all_pass: bool
    path_preserved: bool
    no_forbidden_permission: bool
    cosmetic_differs: bool


def run_seed(base: ScenarioBundle, spec: ScenarioSpec, seed: int) -> SeedResult:
    """Mutate ``base`` for ``seed`` and collect its risk-preservation evidence."""
    mutated = MutationGenerator(base, seed, spec.constraints.max_resources).generate()
    outcomes = {o.label: o.status for o in GraphRiskEngine(mutated, spec).run()}
    base_hash = _graph_hash(base)
    variant_hash = _graph_hash(mutated)
    return SeedResult(
        seed=seed,
        graph_hash=variant_hash,
        node_ids=frozenset(n.id for n in mutated.graph.nodes),
        critical_path_node_ids=critical_path_node_ids(mutated),
        severity_multiset=severity_multiset(mutated),
        finding_ids=finding_ids(mutated),
        finding_families=finding_families(mutated),
        risk_all_pass=all(s is Status.PASS for s in outcomes.values()),
        path_preserved=outcomes.get(PATH_PRESERVED_LABEL) is Status.PASS,
        no_forbidden_permission=outcomes.get(NO_FORBIDDEN_LABEL) is Status.PASS,
        cosmetic_differs=variant_hash != base_hash,
    )


@dataclass
class MutationStressSummary:
    """Aggregate written to ``mutation_summary.json`` (the FXL-N3 deliverable)."""

    seeds_run: int = 0
    validated_variants: int = 0
    path_preserved: int = 0
    no_forbidden_permission: int = 0
    cosmetic_variants: int = 0
    severity_mix_preserved: int = 0
    findings_preserved: int = 0
    families_preserved: int = 0
    distinct_graph_hashes: int = 0
    seed_range: tuple[int, int] = (0, 0)
    terraform_sampled_seeds: list[int] = field(default_factory=list)
    terraform_sampled_valid: int = 0
    terraform_sampling_note: str = ""
    failures: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"

    def write(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json())
        return path


def aggregate(base: ScenarioBundle, results: list[SeedResult]) -> MutationStressSummary:
    """Fold per-seed results into the committed aggregate + record any defects."""
    base_critical = critical_path_node_ids(base)
    base_severity = severity_multiset(base)
    base_ids = finding_ids(base)
    base_families = finding_families(base)
    summary = MutationStressSummary(seeds_run=len(results))
    if results:
        seeds = [r.seed for r in results]
        summary.seed_range = (min(seeds), max(seeds))
    hashes: set[str] = set()
    for r in results:
        hashes.add(r.graph_hash)
        summary.validated_variants += int(r.risk_all_pass)
        summary.no_forbidden_permission += int(r.no_forbidden_permission)
        summary.cosmetic_variants += int(r.cosmetic_differs)
        summary.severity_mix_preserved += int(r.severity_multiset == base_severity)
        summary.findings_preserved += int(r.finding_ids == base_ids)
        summary.families_preserved += int(r.finding_families == base_families)
        _record_path(summary, r, base_critical)
    summary.distinct_graph_hashes = len(hashes)
    return summary


def _record_path(
    summary: MutationStressSummary, r: SeedResult, base_critical: tuple[str, ...]
) -> None:
    """Count path preservation and flag any seed that drops the critical path."""
    ids_present = all(nid in r.node_ids for nid in base_critical)
    preserved = r.path_preserved and r.critical_path_node_ids == base_critical and ids_present
    summary.path_preserved += int(preserved)
    if not preserved:
        summary.failures.append(
            f"seed {r.seed}: critical path NOT preserved "
            f"(path_check={r.path_preserved}, ids_present={ids_present}, "
            f"critical_ids={list(r.critical_path_node_ids)})"
        )
    if not r.no_forbidden_permission:
        summary.failures.append(f"seed {r.seed}: forbidden permission introduced")


def terraform_available() -> bool:
    return tool_probe.detect_tool("terraform")


def terraform_validate_variant(
    base: ScenarioBundle,
    spec: ScenarioSpec,
    seed: int,
    scenario_dir: Path,
    plugin_cache_dir: Path,
) -> Status:
    """Emit a variant to disk and run REAL ``terraform validate`` over it.

    A single shared ``TF_PLUGIN_CACHE_DIR`` means the AWS provider is fetched once and
    symlinked into every variant, so sampling N seeds costs one provider download and
    ~0 extra disk per seed (not ~650 MB each). Returns the terraform-validate status;
    a network/provider hiccup surfaces as WARN (fail-soft), a real syntax/config error
    as FAIL. ``PASS`` is the only "valid" verdict the caller counts.
    """
    mutated = MutationGenerator(base, seed, spec.constraints.max_resources).generate()
    ScenarioArtifacts(ScenarioPaths.from_dir(scenario_dir)).write_all(spec, mutated)
    plugin_cache_dir.mkdir(parents=True, exist_ok=True)
    previous = os.environ.get("TF_PLUGIN_CACHE_DIR")
    os.environ["TF_PLUGIN_CACHE_DIR"] = str(plugin_cache_dir)
    try:
        outcome = external_scans.run_terraform(ScenarioPaths.from_dir(scenario_dir))
    finally:
        if previous is None:
            os.environ.pop("TF_PLUGIN_CACHE_DIR", None)
        else:
            os.environ["TF_PLUGIN_CACHE_DIR"] = previous
    return outcome.status
