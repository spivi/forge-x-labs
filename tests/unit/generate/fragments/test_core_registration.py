"""``@register_core`` and its derived maps (v1.4.0 registration collapse).

Adding a family is now: one fragment module declaring ``scenario_type``,
``cloud``, ``prompt``, ``checklist`` and ``teaching_point`` on the class. These
tests hold the derivation, not the fragment content: every hand-maintained map
that used to duplicate a family's data must read it back from the registry.
"""

from __future__ import annotations

from random import Random
from typing import Any

import pytest

from app.cloudforge.generate.composer_kinds import CORE_KINDS
from app.cloudforge.generate.fragments import base
from app.cloudforge.generate.fragments.base import (
    FragmentBundle,
    core_kind_for,
    core_meta,
    core_scenario_types,
    get_fragment,
    register_core,
)
from app.cloudforge.lab.brief import _PROMPTS
from app.cloudforge.lab.estate import CANONICAL_FINDINGS
from app.cloudforge.models.graph import GraphNode, NodeSecurity, NodeTags, NodeType


@pytest.fixture(autouse=True)
def _isolate_registries() -> Any:
    """Snapshot both registries and restore them after each test.

    ``test_register_core_*`` below registers a throwaway ``test_core_family``
    into the module-global registries; without cleanup it would leak into
    every other test in the process (``core_scenario_types``, ``CORE_KINDS``...).
    """
    registry_snapshot = dict(base._REGISTRY)
    meta_snapshot = dict(base._CORE_META)
    yield
    base._REGISTRY.clear()
    base._REGISTRY.update(registry_snapshot)
    base._CORE_META.clear()
    base._CORE_META.update(meta_snapshot)


def _dummy_bundle(ns: str) -> FragmentBundle:
    node = GraphNode(
        id=f"{ns}/n",
        type=NodeType.S3_BUCKET,
        name="b",
        tags=NodeTags(env="staging", owner="platform-team", app="a"),
        security=NodeSecurity(criticality="low"),
    )
    return FragmentBundle(nodes=[node], edges=[], findings=[], paths=[])


def test_register_core_indexes_by_scenario_type_and_kind() -> None:
    @register_core
    class _TestCoreFamily:
        scenario_type = "test_core_family"
        cloud = "aws"
        prompt = "A test prompt."
        checklist = ("test_core_family", "Test: Core Family")
        teaching_point = "A one-line teaching point."

        def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
            return _dummy_bundle(ns)

    assert "test_core_family" in core_scenario_types()
    assert core_kind_for("test_core_family") == "core.test_core_family"
    assert get_fragment("core.test_core_family").build("frag0", Random(0), {}).nodes[0].id == (
        "frag0/n"
    )
    meta = core_meta("test_core_family")
    assert meta.cloud == "aws"
    assert meta.prompt == "A test prompt."
    assert meta.checklist == ("test_core_family", "Test: Core Family")
    assert meta.teaching_point == "A one-line teaching point."


@pytest.mark.parametrize(
    "missing_attr", ["scenario_type", "cloud", "prompt", "checklist", "teaching_point"]
)
def test_register_core_requires_every_declared_attribute(missing_attr: str) -> None:
    attrs: dict[str, Any] = {
        "scenario_type": "test_incomplete_family",
        "cloud": "aws",
        "prompt": "A test prompt.",
        "checklist": ("test_incomplete_family", "Test"),
        "teaching_point": "A one-line teaching point.",
    }
    del attrs[missing_attr]

    with pytest.raises(TypeError, match=missing_attr):
        register_core(type("_Incomplete", (), attrs))


def test_register_core_requires_a_two_item_checklist_tuple() -> None:
    attrs: dict[str, Any] = {
        "scenario_type": "test_bad_checklist_family",
        "cloud": "aws",
        "prompt": "A test prompt.",
        "checklist": "not-a-tuple",
        "teaching_point": "A one-line teaching point.",
    }

    with pytest.raises(TypeError, match="checklist"):
        register_core(type("_BadChecklist", (), attrs))


def test_composer_kinds_derives_from_the_core_registry() -> None:
    for scenario_type in core_scenario_types():
        assert CORE_KINDS[scenario_type] == core_kind_for(scenario_type)
    assert set(CORE_KINDS) == set(core_scenario_types())


def test_brief_prompts_derive_from_the_core_registry() -> None:
    for scenario_type in core_scenario_types():
        assert _PROMPTS[scenario_type] == core_meta(scenario_type).prompt
    assert set(_PROMPTS) == set(core_scenario_types())


def test_canonical_findings_include_every_core_family_checklist_row() -> None:
    by_id = {entry["id"]: entry for entry in CANONICAL_FINDINGS}
    for scenario_type in core_scenario_types():
        meta = core_meta(scenario_type)
        finding_id, label = meta.checklist
        assert by_id[finding_id] == {"id": finding_id, "label": label, "cloud": meta.cloud}
