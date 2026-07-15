"""Failure capture + minimization (design doc §4.2, error class FAIL).

``capture_failure`` preserves the raw artifacts already written for a failed
scenario, plus its logs and the causing exception, under
``failures/raw/<scenario_id>/`` — a COPY, never a move, so the original
``scenarios/<scenario_id>/`` tree is untouched. ``minimize`` shrinks a captured
failure to the smallest reproducer (smaller scale, then disabling one variation
axis at a time) into ``failures/minimized/<scenario_id>/`` and NEVER deletes or
mutates the raw originals (hard AC).
"""

from __future__ import annotations

import shutil
import tempfile
import traceback
from pathlib import Path

from app.cloudforge.generate.composer import GraphComposer
from app.cloudforge.io.paths import ScenarioPaths
from app.cloudforge.models.scenario import ScenarioSpec
from app.cloudforge.pipeline.artifacts import ScenarioArtifacts
from app.cloudforge.validate.orchestrator import run_validations

_SMALLER_SCALE = {
    "xlarge": "large",
    "large": "medium",
    "medium": "small",
    "small": "tiny",
    "tiny": "tiny",
}


def capture_failure(run_dir: Path, scenario_id: str, scenario_dir: Path, exc: Exception) -> str:
    """Copy ``scenario_dir`` (if it exists) plus a log/exception file into
    ``failures/raw/<scenario_id>/``. Returns the failure id (== scenario_id)."""
    raw_dir = run_dir / "failures" / "raw" / scenario_id
    if scenario_dir.exists():
        shutil.copytree(scenario_dir, raw_dir, dirs_exist_ok=True)
    else:
        raw_dir.mkdir(parents=True, exist_ok=True)
    _write_failure_log(raw_dir, exc)
    return scenario_id


def _write_failure_log(raw_dir: Path, exc: Exception) -> None:
    log_path = raw_dir / "failure.log"
    body = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    log_path.write_text(f"{exc}\n\n{body}", encoding="utf-8")


def minimize(run_dir: Path, scenario_id: str, spec: ScenarioSpec, seed: int) -> Path:
    """Shrink the failure recorded for ``scenario_id`` to a smaller reproducer that
    still fails validation, writing ONLY the accepted result under
    ``failures/minimized/<id>/``. Best-effort single pass (each candidate is derived
    from the original spec — one scale-shrink, then each axis disabled independently —
    so it finds *a* smaller reproducer, not necessarily the minimal one). Trial
    candidates are validated in a throwaway temp dir so no stale artifacts (e.g.
    orphaned per-resource ``.tf`` files) leak into the minimized output. Never touches
    ``failures/raw/<id>/``."""
    minimized_dir = run_dir / "failures" / "minimized" / scenario_id
    candidate = spec
    with tempfile.TemporaryDirectory() as scratch:
        for shrunk in _shrink_candidates(spec):
            if not _still_fails(shrunk, seed, Path(scratch) / "trial"):
                break
            candidate = shrunk
    _write_candidate(candidate, seed, minimized_dir)
    return minimized_dir


def _shrink_candidates(spec: ScenarioSpec) -> list[ScenarioSpec]:
    candidates = [spec.model_copy(update={"scale_profile": _SMALLER_SCALE[spec.scale_profile]})]
    for axis in spec.variation_axes:
        axes = {**spec.variation_axes, axis: "0"}
        candidates.append(spec.model_copy(update={"variation_axes": axes}))
    return candidates


def _still_fails(spec: ScenarioSpec, seed: int, scratch_dir: Path) -> bool:
    try:
        _write_candidate(spec, seed, scratch_dir)
    except Exception:  # noqa: BLE001 - composer/write errors count as "still fails"
        return True
    report = run_validations(scratch_dir)
    return report.has_failure


def _write_candidate(spec: ScenarioSpec, seed: int, dest: Path) -> None:
    bundle = GraphComposer(spec, seed=seed).generate()
    ScenarioArtifacts(ScenarioPaths.from_dir(dest)).write_all(spec, bundle)


__all__ = ["capture_failure", "minimize"]
