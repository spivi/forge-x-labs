"""Write a student/instructor lab pack from a scenario spec + seed."""

from __future__ import annotations

import shutil
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from app.cloudforge.errors import UnknownEngineError
from app.cloudforge.generate.base import ScenarioBundle
from app.cloudforge.generate.composer import GraphComposer
from app.cloudforge.generate.template_generator import TemplateGenerator
from app.cloudforge.io.loaders import dump_json, dump_yaml, write_text
from app.cloudforge.io.paths import ScenarioPaths
from app.cloudforge.lab.brief import _DEFAULT_PROMPT, _PROMPTS, render_brief
from app.cloudforge.lab.estate import render_estate_html
from app.cloudforge.lab.paths import LabPaths
from app.cloudforge.lab.strip import strip_graph
from app.cloudforge.models.scenario import ScenarioSpec
from app.cloudforge.pipeline.artifacts import ScenarioArtifacts
from app.cloudforge.report.renderer import ReportRenderer


class LabRequest(BaseModel):
    """Inputs for ``write_lab`` (keeps the function within the param limit)."""

    model_config = ConfigDict(extra="forbid")

    spec: ScenarioSpec
    seed: int = 0
    engine: str = "composer"


def write_lab(request: LabRequest, out_dir: LabPaths) -> ScenarioBundle:
    """Generate the bundle and write both packs. Returns the bundle for tests."""
    bundle = _build_bundle(request)
    out_dir.student.mkdir(parents=True, exist_ok=True)
    out_dir.instructor.mkdir(parents=True, exist_ok=True)
    _write_instructor(out_dir, request.spec, bundle)
    _write_student(out_dir, request.spec, bundle)
    return bundle


def write_challenge_workbench(request: LabRequest, out_path: Path) -> Path:
    """Generate a single self-contained interactive challenge HTML workbench."""
    bundle = _build_bundle(request)
    estate = strip_graph(bundle.graph)
    prompt = _PROMPTS.get(request.spec.scenario_type, _DEFAULT_PROMPT)
    html = render_estate_html(
        estate, prompt=prompt, title=f"Challenge · {request.spec.scenario_type}"
    )
    target = out_path if out_path.suffix == ".html" else out_path / "challenge.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    write_text(target, html)
    return target


def _build_bundle(request: LabRequest) -> ScenarioBundle:
    if request.engine == "composer":
        return GraphComposer(request.spec, seed=request.seed).generate()
    if request.engine == "template":
        return TemplateGenerator().generate(request.spec)
    raise UnknownEngineError(f"unknown engine {request.engine!r}; choose 'template' or 'composer'")


def _write_instructor(out_dir: LabPaths, spec: ScenarioSpec, bundle: ScenarioBundle) -> None:
    ScenarioArtifacts(ScenarioPaths.from_dir(out_dir.instructor)).write_all(spec, bundle)
    ReportRenderer(out_dir.instructor).render_to_file()
    dump_json(out_dir.grade_key, _grade_key(bundle))


def _write_student(out_dir: LabPaths, spec: ScenarioSpec, bundle: ScenarioBundle) -> None:
    estate = strip_graph(bundle.graph)
    dump_yaml(out_dir.student / "scenario.yaml", spec.model_dump())
    dump_json(out_dir.estate_json, estate)
    write_text(out_dir.brief, render_brief(spec, bundle.graph))
    prompt = _PROMPTS.get(spec.scenario_type, _DEFAULT_PROMPT)
    title = f"Lab · {spec.scenario_type}"
    write_text(out_dir.estate_html, render_estate_html(estate, prompt=prompt, title=title))
    terraform = ScenarioPaths.from_dir(out_dir.instructor).terraform_dir
    shutil.copytree(terraform, out_dir.student / "terraform", dirs_exist_ok=True)


def _grade_key(bundle: ScenarioBundle) -> dict[str, object]:
    return {
        "paths": [
            {"id": path.id, "nodes": list(path.nodes)} for path in bundle.ground_truth.paths
        ],
        "finding_families": sorted({f.family.value for f in bundle.findings.findings}),
    }
