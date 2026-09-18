"""Support helpers for the CLI-level mutation determinism/risk-preservation stress
suite (issue #114).

Distinct from ``mutation_stress_support.py`` (in-memory, single-family,
100 seeds): this module drives the REAL Typer CLI (``generate`` twice on disk,
``validate``, ``report``) across BOTH scenario families so the byte-identical
assertion (S10) covers the actual emitted artifact files a user gets — not just an
in-process re-serialization — and the risk-preservation assertion (S11) is checked
against the report's own ``## Validation`` section (the wave-1 fix), not a bespoke
in-memory recomputation.

Everything here is a pure/importable helper so the test module stays declarative.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from typer.testing import CliRunner

from app.cli import app
from app.cloudforge import constants
from app.cloudforge.io.loaders import load_json
from app.cloudforge.io.paths import ScenarioPaths
from app.cloudforge.validate import tool_probe
from app.cloudforge.validate.orchestrator import run_local_validations
from app.cloudforge.validate.results import Status

_runner = CliRunner()

# The two families the ticket requires ("BOTH families x seeds").
FAMILIES: tuple[str, ...] = ("ci_cd_iam_chain", "public_data_exposure")
FAMILY_SPECS: dict[str, str] = {
    "ci_cd_iam_chain": "examples/ci_cd_iam_chain.yaml",
    "public_data_exposure": "examples/public_data_exposure.yaml",
}

# The three ground-truth artifact files S10 requires to be byte-identical.
_COMPARED_FILES: tuple[str, ...] = (
    constants.GRAPH_FILENAME,
    constants.EXPECTED_FINDINGS_FILENAME,
    constants.GROUND_TRUTH_FILENAME,
)


def _spec_path(family: str) -> str:
    return FAMILY_SPECS[family]


def _generate(family: str, seed: int, out: Path) -> None:
    """Invoke the real CLI ``generate --mutate-seed`` command; skip external tools."""
    result = _runner.invoke(
        app,
        ["generate", _spec_path(family), "--out", str(out), "--mutate-seed", str(seed)],
    )
    assert result.exit_code == 0, (
        f"generate failed for family={family} seed={seed}: {result.output}"
    )


def _validate(out: Path) -> tuple[bool, str]:
    """Run the deterministic, stdlib-only local validation over the on-disk variant.

    Deliberately uses :func:`run_local_validations` (schema + graph-risk engine —
    the same subset the report itself consults for its ``## Validation`` section)
    rather than the CLI ``validate`` command's ``run_validations``, which also
    shells out to any LOCALLY INSTALLED terraform/checkov/opa. Those external
    scanners are optional, environment-dependent, and (at ~seconds each) make a
    1,000-seed x 2-family sweep infeasible — and would make this stress suite's
    pass/fail depend on what happens to be on the machine running it, not on the
    ``MutationGenerator`` contract (S10/S11) it exists to prove. The graph-risk
    engine is the authoritative, deterministic risk-preservation check either way.
    """
    report = run_local_validations(out)
    ok = not report.has_failure
    detail = "; ".join(o.render() for o in report.outcomes if o.status is not Status.PASS)
    return ok, detail


def _report(out: Path) -> str:
    """Invoke the real CLI ``report`` command and return the rendered report text."""
    result = _runner.invoke(app, ["report", str(out)])
    assert result.exit_code == 0, f"report failed for {out}: {result.output}"
    paths = ScenarioPaths.from_dir(out)
    return paths.report.read_text()


def _read_compared_bytes(out: Path) -> dict[str, bytes]:
    return {name: (out / name).read_bytes() for name in _COMPARED_FILES}


def _forbidden_perm_hit(out: Path) -> str | None:
    """Return the first forbidden action found in the emitted graph, or None.

    Scans the on-disk ``graph.json`` directly (not the in-memory bundle) so this
    checks the ACTUAL artifact a downstream scanner/consumer would read.
    """
    import fnmatch

    graph = load_json(ScenarioPaths.from_dir(out).graph)
    for node in graph.get("nodes", []):
        actions = node.get("attributes", {}).get("actions", [])
        if isinstance(actions, str):
            actions = [actions]
        for action in actions:
            for pattern in constants.FORBIDDEN_PERMISSION_PATTERNS:
                if fnmatch.fnmatch(action, pattern):
                    return f"{node.get('id')}:{action}"
    return None


def _cosmetic_signature(out: Path) -> tuple[str, ...]:
    """A signature of the mutable cosmetic surface (names + tag values) for
    diversity comparison across seeds — deliberately excludes ids/edges/security."""
    graph = load_json(ScenarioPaths.from_dir(out).graph)
    sig: list[str] = []
    for node in sorted(graph.get("nodes", []), key=lambda n: n["id"]):
        tags = node.get("tags", {})
        sig.append(node.get("name", ""))
        sig.append(str(tags.get("env", "")))
        sig.append(str(tags.get("owner", "")))
        sig.append(str(tags.get("app", "")))
    return tuple(sig)


def _report_all_pass(report_text: str) -> bool:
    """True iff the report's own ``## Validation`` section shows all-PASS.

    Mirrors the wave-1 fix (report re-runs local validation and renders a
    ``## Validation`` section): a risk-preserving mutation must show the
    "All validation checks passed" banner and never the FAILED banner.
    """
    if "## Validation" not in report_text:
        return False
    if "THIS SCENARIO FAILED VALIDATION" in report_text:
        return False
    return "All validation checks passed" in report_text


@dataclass(frozen=True)
class CliSeedResult:
    """Per-(family, seed) evidence collected by driving the real CLI twice."""

    family: str
    seed: int
    byte_identical: bool
    diverging_files: tuple[str, ...]
    validate_ok: bool
    report_all_pass: bool
    findings_and_ground_truth_preserved: bool
    forbidden_perm_hit: str | None
    cosmetic_signature: tuple[str, ...]


def _base_out(family: str, tmp_root: Path) -> Path:
    """The un-mutated base generation for ``family`` (memoized per tmp_root)."""
    out = tmp_root / family / "_base"
    if not out.exists():
        result = _runner.invoke(app, ["generate", _spec_path(family), "--out", str(out)])
        assert result.exit_code == 0, f"base generate failed for {family}: {result.output}"
    return out


def _findings_and_ground_truth_preserved(base_out: Path, variant_out: Path) -> bool:
    """S11: expected findings + ground-truth paths are UNCHANGED vs the un-mutated
    base — the exact clause the ticket calls out ("critical paths + expected
    findings preserved vs the un-mutated base"), not merely stable across repeats.
    """
    for name in (constants.EXPECTED_FINDINGS_FILENAME, constants.GROUND_TRUTH_FILENAME):
        if (base_out / name).read_bytes() != (variant_out / name).read_bytes():
            return False
    return True


def run_cli_seed(family: str, seed: int, tmp_root: Path) -> CliSeedResult:
    """Generate ``family``+``seed`` TWICE via the real CLI, then validate + report.

    S10: the two generate runs must produce byte-identical graph/findings/
    ground-truth files. S11: the risk-preserving assertions (validate exit 0,
    report all-PASS, findings/ground-truth preserved vs the un-mutated base, no
    forbidden perm) are checked on the SECOND run's output.
    """
    base_out = _base_out(family, tmp_root)
    out_a = tmp_root / family / f"seed_{seed:04d}_a"
    out_b = tmp_root / family / f"seed_{seed:04d}_b"
    _generate(family, seed, out_a)
    _generate(family, seed, out_b)

    bytes_a = _read_compared_bytes(out_a)
    bytes_b = _read_compared_bytes(out_b)
    diverging = tuple(name for name in _COMPARED_FILES if bytes_a[name] != bytes_b[name])

    validate_ok, _ = _validate(out_b)
    report_text = _report(out_b)
    forbidden_hit = _forbidden_perm_hit(out_b)

    return CliSeedResult(
        family=family,
        seed=seed,
        byte_identical=not diverging,
        diverging_files=diverging,
        validate_ok=validate_ok,
        report_all_pass=_report_all_pass(report_text),
        findings_and_ground_truth_preserved=_findings_and_ground_truth_preserved(base_out, out_b),
        forbidden_perm_hit=forbidden_hit,
        cosmetic_signature=_cosmetic_signature(out_b),
    )


@dataclass
class MutationSummary:
    """The aggregate written to ``mutation_summary.json``.

    Field names match the ticket's required aggregate: validated, path-preserved,
    forbidden-perm-hit counts, and distinct-cosmetic-variant counts — plus enough
    breakdown (per family, seed range, deterministic count) to be reviewable.
    """

    families: list[str] = field(default_factory=list)
    seeds_per_family: int = 0
    seed_range: tuple[int, int] = (0, 0)
    total_variants: int = 0
    deterministic: int = 0
    validated: int = 0
    path_preserved: int = 0
    forbidden_perm_hits: int = 0
    distinct_cosmetic_variants: int = 0
    per_family_distinct_cosmetic_variants: dict[str, int] = field(default_factory=dict)
    nondeterminism_failures: list[str] = field(default_factory=list)
    validation_failures: list[str] = field(default_factory=list)
    forbidden_perm_failures: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"

    def write(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json())
        return path


def aggregate(results: list[CliSeedResult], seeds: range) -> MutationSummary:
    """Fold per-(family, seed) CLI results into the committed aggregate."""
    families = sorted({r.family for r in results})
    summary = MutationSummary(
        families=families,
        seeds_per_family=len(seeds),
        seed_range=(seeds.start, seeds.stop - 1) if len(seeds) else (0, 0),
        total_variants=len(results),
    )
    signatures_by_family: dict[str, set[tuple[str, ...]]] = {f: set() for f in families}
    for r in results:
        signatures_by_family[r.family].add(r.cosmetic_signature)
        summary.deterministic += int(r.byte_identical)
        if not r.byte_identical:
            summary.nondeterminism_failures.append(
                f"{r.family} seed {r.seed}: diverging files {list(r.diverging_files)}"
            )
        validated_ok = r.validate_ok and r.report_all_pass
        summary.validated += int(validated_ok)
        if not validated_ok:
            summary.validation_failures.append(
                f"{r.family} seed {r.seed}: validate_ok={r.validate_ok} "
                f"report_all_pass={r.report_all_pass}"
            )
        summary.path_preserved += int(r.findings_and_ground_truth_preserved)
        if not r.findings_and_ground_truth_preserved:
            summary.validation_failures.append(
                f"{r.family} seed {r.seed}: findings/ground-truth diverged from base"
            )
        if r.forbidden_perm_hit is not None:
            summary.forbidden_perm_hits += 1
            summary.forbidden_perm_failures.append(
                f"{r.family} seed {r.seed}: forbidden perm {r.forbidden_perm_hit}"
            )
    summary.per_family_distinct_cosmetic_variants = {
        f: len(sigs) for f, sigs in signatures_by_family.items()
    }
    summary.distinct_cosmetic_variants = sum(
        summary.per_family_distinct_cosmetic_variants.values()
    )
    return summary


def terraform_probe_available() -> bool:
    return tool_probe.detect_tool("terraform")
