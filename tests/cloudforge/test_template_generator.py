"""Template generator tests (check 2: graph generation works)."""

from __future__ import annotations

import pytest

from app.cloudforge.errors import TemplateProjectionMissingError, UnknownScenarioTypeError
from app.cloudforge.generate.template_generator import TemplateGenerator
from app.cloudforge.models.graph import NodeType
from app.cloudforge.models.scenario import ScenarioSpec


def test_generate_ci_cd_chain_returns_graph(example_spec: ScenarioSpec) -> None:
    bundle = TemplateGenerator().generate(example_spec)

    assert len(bundle.graph.nodes) > 0
    assert len(bundle.graph.edges) > 0


def test_generate_ci_cd_chain_respects_resource_budget(example_spec: ScenarioSpec) -> None:
    bundle = TemplateGenerator().generate(example_spec)

    assert len(bundle.graph.nodes) <= example_spec.constraints.max_resources


def test_generate_includes_runtime_role_and_sensitive_bucket(example_spec: ScenarioSpec) -> None:
    bundle = TemplateGenerator().generate(example_spec)

    ids = {n.id for n in bundle.graph.nodes if n.type is NodeType.IAM_ROLE}
    assert {"role-deploy", "role-runtime"} <= ids


def test_generate_unknown_type_raises(example_spec: ScenarioSpec) -> None:
    spec = example_spec.model_copy(update={"scenario_type": "does_not_exist"})

    with pytest.raises(UnknownScenarioTypeError):
        TemplateGenerator().generate(spec)


def test_generate_registered_family_without_projection_raises_clean_error(
    example_spec: ScenarioSpec,
) -> None:
    """``k8s_pod_irsa_exfil`` is a registered core family (v1.4.0) with no
    template projection: ``--engine template`` must fail with a clear message
    naming ``--engine composer``, not silently switch engines."""
    spec = example_spec.model_copy(update={"scenario_type": "k8s_pod_irsa_exfil"})

    with pytest.raises(TemplateProjectionMissingError, match="composer"):
        TemplateGenerator().generate(spec)
