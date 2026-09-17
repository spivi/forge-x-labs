"""Brief must not leak the answer key."""

from __future__ import annotations

from pathlib import Path

from app.cloudforge.generate.composer import GraphComposer
from app.cloudforge.io.loaders import load_yaml
from app.cloudforge.lab.brief import render_brief
from app.cloudforge.models.scenario import ScenarioSpec


def test_brief_does_not_name_can_pass_role() -> None:
    data = load_yaml(Path("examples/ci_cd_iam_chain.yaml"))
    spec = ScenarioSpec.model_validate(data)
    bundle = GraphComposer(spec, seed=17).generate()
    text = render_brief(spec, bundle.graph)
    assert "can_pass_role" not in text
    for path in bundle.ground_truth.paths:
        assert " → ".join(path.nodes) not in text
        assert path.explanation not in text
    for finding in bundle.findings.findings:
        assert finding.remediation not in text
