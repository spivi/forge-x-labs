"""Facilitator pack: one identity-federation lesson, three clouds, unique copies."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from app.cloudforge.errors import CloudforgeError
from app.cloudforge.io.loaders import dump_json, load_yaml, write_text
from app.cloudforge.lab.cohort import seed_for
from app.cloudforge.lab.pack import LabRequest, write_lab
from app.cloudforge.lab.paths import LabPaths
from app.cloudforge.models.scenario import ScenarioSpec

TRACKS: dict[str, tuple[str, ...]] = {
    "identity_federation": (
        "k8s_pod_irsa_exfil",
        "azure_imds_keyvault_harvest",
        "gcp_workload_identity_federation",
    ),
}

_AGENDA = """# Roundtable: {track}

CPU-only. No cloud account. Never `terraform apply`.

## Why this track

Same attack class on three vendors. A workload proves who it is to a cloud
IAM system, then reaches data. Students do not all get the same estate.
They get the same lesson.

- Kubernetes: a pod federates into AWS IAM (IRSA) and reads a bucket.
- Azure: an App Service managed identity reaches Key Vault.
- GCP: a CI identity federates through a Workload Identity Pool into GCS.

## 90 minutes

1. 10 min. Identity federation in one sentence. A workload, not a human, is
   trusted into IAM.
2. 40 min. Each person opens `student/estate.html`. Find a path from an
   identity to data. Write the path as node ids, then a short paragraph.
3. 30 min. Share-out. What was common across the three clouds? What was
   vendor-specific? Do not open `instructor/` yet.
4. 10 min. Grade the node-id guesses:

   `cloudforge grade <name>/ --submission <name>.yaml`

## Roster

| name | family | seed | pack |
|---|---|---|---|
{rows}

## Do not

- Open `instructor/` until after share-out.
- Run `terraform apply`.
- Hand everyone the same seed. Unique copies are the point.
"""


class RoundtableRequest(BaseModel):
    """Inputs for ``write_roundtable``."""

    model_config = ConfigDict(extra="forbid")

    track: str = "identity_federation"
    names: list[str]
    engine: str = "composer"


def write_roundtable(request: RoundtableRequest, out_dir: Path) -> Path:
    """Write per-student labs, roster.json, and facilitator.md."""
    families = TRACKS.get(request.track)
    if families is None:
        known = ", ".join(sorted(TRACKS))
        raise CloudforgeError(f"unknown roundtable track {request.track!r}; known: {known}")
    if not request.names:
        raise CloudforgeError("roundtable needs at least one student name")
    out_dir.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, object]] = []
    for index, name in enumerate(request.names):
        family = families[index % len(families)]
        spec = ScenarioSpec.model_validate(load_yaml(_example(family)))
        seed = seed_for(name)
        lab = LabRequest(spec=spec, seed=seed, engine=request.engine)
        write_lab(lab, LabPaths.from_dir(out_dir / name))
        entries.append({"name": name, "seed": seed, "family": family, "dir": name})
    dump_json(out_dir / "roster.json", {"track": request.track, "entries": entries})
    write_text(out_dir / "facilitator.md", _facilitator(request.track, entries))
    return out_dir / "facilitator.md"


def _example(family: str) -> Path:
    name = f"{family}.yaml"
    rooted = Path(__file__).resolve().parents[3] / "examples" / name
    cwd = Path("examples") / name
    path = rooted if rooted.is_file() else cwd
    if not path.is_file():
        raise CloudforgeError(f"missing example spec examples/{name}")
    return path


def _facilitator(track: str, entries: list[dict[str, object]]) -> str:
    rows = "\n".join(
        f"| {e['name']} | `{e['family']}` | {e['seed']} | `{e['dir']}/student/` |" for e in entries
    )
    return _AGENDA.format(track=track, rows=rows)
