"""Hardcoded ``cross_account_trust`` scenario data (template engine).

The fragment ``core.cross_account_trust`` is the source of truth; this module
projects it with an empty namespace so template ids stay unprefixed.
"""

from __future__ import annotations

from random import Random

from app.cloudforge.generate.fragments.base import FragmentBundle
from app.cloudforge.generate.fragments.core_cross_account import CrossAccountTrust
from app.cloudforge.models.findings import ExpectedFindings, GroundTruthPaths
from app.cloudforge.models.graph import ScenarioGraph


def _bundle() -> FragmentBundle:
    return CrossAccountTrust().build("", Random(0), {})


def build_graph() -> ScenarioGraph:
    bundle = _bundle()
    return ScenarioGraph(nodes=bundle.nodes, edges=bundle.edges)


def build_findings() -> ExpectedFindings:
    return ExpectedFindings(findings=_bundle().findings)


def build_ground_truth() -> GroundTruthPaths:
    return GroundTruthPaths(paths=_bundle().paths)
