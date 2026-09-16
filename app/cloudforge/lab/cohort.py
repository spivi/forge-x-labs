"""Cohort helper: one lab per student name, stable seed, roster + results."""

from __future__ import annotations

from pathlib import Path
from zlib import adler32

from pydantic import BaseModel, ConfigDict

from app.cloudforge.io.loaders import dump_json, load_json, load_yaml, write_text
from app.cloudforge.lab.grade import grade_submission
from app.cloudforge.lab.pack import LabRequest, write_lab
from app.cloudforge.lab.paths import LabPaths
from app.cloudforge.lab.submission import LabSubmission
from app.cloudforge.models.scenario import ScenarioSpec

_SEED_MOD = 10_000


class CohortRequest(BaseModel):
    """Inputs for ``write_cohort``."""

    model_config = ConfigDict(extra="forbid")

    spec: ScenarioSpec
    names: list[str]
    engine: str = "composer"


def seed_for(name: str) -> int:
    """Stable seed from a student name (not ``hash()`` — that is process-salted)."""
    return adler32(name.encode("utf-8")) % _SEED_MOD


def write_cohort(request: CohortRequest, out_dir: Path) -> Path:
    """Write ``out_dir/<name>/`` for each student and ``out_dir/roster.json``."""
    out_dir.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, object]] = []
    for name in request.names:
        seed = seed_for(name)
        lab = LabRequest(spec=request.spec, seed=seed, engine=request.engine)
        write_lab(lab, LabPaths.from_dir(out_dir / name))
        entries.append({"name": name, "seed": seed, "dir": name})
    roster_path = out_dir / "roster.json"
    dump_json(roster_path, {"entries": entries})
    return roster_path


def load_names(path: Path) -> list[str]:
    """One student name per line; blank lines skipped."""
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def grade_cohort(cohort_dir: Path, submissions_dir: Path) -> Path:
    """Grade ``submissions_dir/<name>.yaml`` for each roster row; write results.md."""
    roster = load_json(cohort_dir / "roster.json")
    raw_entries = roster.get("entries")
    entries = raw_entries if isinstance(raw_entries, list) else []
    header = "| name | seed | paths hit | paths miss | findings hit | extras |"
    lines = ["# Cohort results", "", header, "|---|---|---|---|---|---|"]
    for item in entries:
        if not isinstance(item, dict):
            continue
        lines.append(_result_row(cohort_dir, submissions_dir, item))
    results = cohort_dir / "results.md"
    write_text(results, "\n".join(lines) + "\n")
    return results


def _result_row(cohort_dir: Path, submissions_dir: Path, item: dict[str, object]) -> str:
    name = str(item.get("name", ""))
    seed = item.get("seed", "")
    guess_path = submissions_dir / f"{name}.yaml"
    if not guess_path.is_file():
        return f"| {name} | {seed} | — | — | — | no submission |"
    key = load_json(LabPaths.from_dir(cohort_dir / name).grade_key)
    result = grade_submission(key, LabSubmission.model_validate(load_yaml(guess_path)))
    return (
        f"| {name} | {seed} | {len(result.path_hits)} | {len(result.path_misses)} | "
        f"{len(result.finding_hits)} | {len(result.extras)} |"
    )
