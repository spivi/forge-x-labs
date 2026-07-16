"""``replay`` — proves a manifest entry's key artifacts are byte-reproducible.

Re-runs the seeded fragment plan for one scenario into a fresh temp directory,
hashes ``graph.json``/``expected_findings.json``/``ground_truth_paths.json``, and
compares against the same files recorded in the run's manifest/artifact tree.
Determinism holds because the composer's ``Random(seed)`` is the only randomness
(design doc §6) — no wall-clock/PID/global RNG is read here or in the composer.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

from app.cloudforge.errors import CloudforgeError
from app.cloudforge.generate.composer import GraphComposer
from app.cloudforge.io.loaders import load_yaml
from app.cloudforge.io.paths import ScenarioPaths
from app.cloudforge.models.scenario import ScenarioSpec
from app.cloudforge.pipeline.artifacts import ScenarioArtifacts
from app.cloudforge.variation.models import RunManifest, ScenarioManifestEntry

_HASHED_FILES = ("graph", "expected_findings", "ground_truth_paths")


def replay(run_dir: Path | str, scenario_id: str) -> bool:
    """Regenerate ``scenario_id`` from ``run_dir``'s manifest and compare hashes
    of its key artifacts to the originals. ``True`` iff byte-identical."""
    run_dir = Path(run_dir)
    entry = _find_entry(run_dir, scenario_id)
    original_dir = run_dir / entry.artifact_dir  # artifact_dir is relative to run_dir
    with tempfile.TemporaryDirectory() as tmp:
        fresh_dir = Path(tmp) / scenario_id
        _regenerate(original_dir, entry.seed, fresh_dir)
        return _hashes_match(original_dir, fresh_dir)


def _find_entry(run_dir: Path, scenario_id: str) -> ScenarioManifestEntry:
    manifest = RunManifest.model_validate(json.loads((run_dir / "manifest.json").read_text()))
    for entry in manifest.entries:
        if entry.scenario_id == scenario_id:
            return entry
    raise CloudforgeError(f"no manifest entry for scenario_id={scenario_id!r}")


def _regenerate(original_dir: Path, seed: int, fresh_dir: Path) -> None:
    scenario_yaml = ScenarioPaths.from_dir(original_dir).scenario_yaml
    spec = ScenarioSpec.model_validate(load_yaml(scenario_yaml))
    bundle = GraphComposer(spec, seed=seed).generate()
    ScenarioArtifacts(ScenarioPaths.from_dir(fresh_dir)).write_all(spec, bundle)


def _hashes_match(original_dir: Path, fresh_dir: Path) -> bool:
    original_paths = ScenarioPaths.from_dir(original_dir)
    fresh_paths = ScenarioPaths.from_dir(fresh_dir)
    for name in _HASHED_FILES:
        original_file = getattr(original_paths, name)
        fresh_file = getattr(fresh_paths, name)
        if _sha256(original_file) != _sha256(fresh_file):
            return False
    return True


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


__all__ = ["replay"]
