"""``cloudforge new-family``: the fragment + example scaffold (v1.4.0 task 2).

The writer tests are unit-level; ``test_scaffolded_family_passes_the_integrity_net``
is the smoke test task 2 calls for: it runs the real CLI command into a temp
copy of the package, then generates seeds 0 and 17 and checks the same
schema + graph-risk validators the composer integrity net runs, with no edits
to the generated fragment.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from app.cloudforge.generate.scaffold import ScaffoldError, new_family

_REPO_ROOT = Path(__file__).resolve().parents[2]

_VALIDATE_SCRIPT = """
from pathlib import Path
from app.cloudforge.io.loaders import load_yaml
from app.cloudforge.io.paths import ScenarioPaths
from app.cloudforge.generate.composer import GraphComposer
from app.cloudforge.models.scenario import ScenarioSpec
from app.cloudforge.pipeline.artifacts import ScenarioArtifacts
from app.cloudforge.validate.orchestrator import run_local_validations

spec = ScenarioSpec.model_validate(load_yaml(Path("examples/{scenario_type}.yaml")))
for seed in (0, 17):
    bundle = GraphComposer(spec, seed=seed).generate()
    out = Path(f"out_{{seed}}")
    ScenarioArtifacts(ScenarioPaths.from_dir(out)).write_all(spec, bundle)
    report = run_local_validations(out)
    fails = [o.render() for o in report.outcomes if o.status.value == "FAIL"]
    assert not fails, (seed, fails)
print("OK")
"""


def test_new_family_refuses_bad_scenario_type(tmp_path: Path) -> None:
    with pytest.raises(ScaffoldError, match="lower_snake_case"):
        new_family("NotSnakeCase", "aws", "A title", tmp_path)


def test_new_family_refuses_unknown_cloud(tmp_path: Path) -> None:
    with pytest.raises(ScaffoldError, match="cloud"):
        new_family("a_family", "oracle", "A title", tmp_path)


def test_new_family_refuses_empty_title(tmp_path: Path) -> None:
    with pytest.raises(ScaffoldError, match="title"):
        new_family("a_family", "aws", "   ", tmp_path)


def test_new_family_writes_fragment_and_example(tmp_path: Path) -> None:
    fragment_path, example_path = new_family("widget_leak", "aws", "Widget leak", tmp_path)
    fragment_text = fragment_path.read_text(encoding="utf-8")
    assert "TODO" not in fragment_text
    assert "register_core" in fragment_text
    assert 'scenario_type = "widget_leak"' in fragment_text
    assert "scenario_type: widget_leak" in example_path.read_text(encoding="utf-8")


def test_new_family_refuses_to_overwrite_the_fragment(tmp_path: Path) -> None:
    new_family("widget_leak", "aws", "Widget leak", tmp_path)
    with pytest.raises(ScaffoldError, match="refusing to overwrite"):
        new_family("widget_leak", "aws", "Widget leak", tmp_path)


@pytest.mark.parametrize("cloud", ["aws", "azure", "gcp", "k8s"])
def test_scaffolded_family_passes_the_integrity_net_as_generated(
    tmp_path: Path, cloud: str
) -> None:
    checkout = tmp_path / "checkout"
    shutil.copytree(_REPO_ROOT / "app", checkout / "app")
    scenario_type = f"smoke_{cloud}_family"

    scaffold = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.cli",
            "new-family",
            scenario_type,
            "--cloud",
            cloud,
            "--title",
            "Smoke test family",
            "--root",
            str(checkout),
        ],
        cwd=checkout,
        capture_output=True,
        text=True,
    )
    assert scaffold.returncode == 0, scaffold.stdout + scaffold.stderr

    validate = subprocess.run(
        [sys.executable, "-c", _VALIDATE_SCRIPT.format(scenario_type=scenario_type)],
        cwd=checkout,
        capture_output=True,
        text=True,
    )
    assert validate.returncode == 0, validate.stdout + validate.stderr
    assert "OK" in validate.stdout
