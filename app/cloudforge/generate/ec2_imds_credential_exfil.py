"""Hardcoded ``ec2_imds_credential_exfil`` scenario data (template engine)."""

from __future__ import annotations

from random import Random

from app.cloudforge.generate.fragments.base import FragmentBundle
from app.cloudforge.generate.fragments.core_ec2_imds import Ec2ImdsCredentialExfil
from app.cloudforge.models.findings import ExpectedFindings, GroundTruthPaths
from app.cloudforge.models.graph import ScenarioGraph


def _bundle() -> FragmentBundle:
    return Ec2ImdsCredentialExfil().build("", Random(0), {})


def build_graph() -> ScenarioGraph:
    bundle = _bundle()
    return ScenarioGraph(nodes=bundle.nodes, edges=bundle.edges)


def build_findings() -> ExpectedFindings:
    return ExpectedFindings(findings=_bundle().findings)


def build_ground_truth() -> GroundTruthPaths:
    return GroundTruthPaths(paths=_bundle().paths)
