"""``cloudforge new-family``: the fragment + example scaffold for a new family.

Since the registration collapse (v1.4.0), a family is one core fragment module
and one example spec (see ``fragments/base.py``): the ``fragments`` package
auto-imports every ``core_*.py`` file it finds, and every other hand-maintained
map (the composer's scenario_type -> kind map, the student brief prompt, the
workbench checklist row, the README teaching-point table) derives from the
class attributes that module declares. This module writes both files from a
template, so dropping the generated fragment into ``fragments/`` and running
the tests is the whole registration path.
"""

from __future__ import annotations

import re
from pathlib import Path

_CLOUDS: tuple[str, ...] = ("aws", "azure", "gcp", "k8s")

_VALID_SCENARIO_TYPE = re.compile(r"^[a-z][a-z0-9_]*$")

# cloud -> (entry NodeType name, entry description, resource NodeType name,
# resource description). The scaffold's path is always the same three-node
# shape (entry exposes resource, resource stores the sink data) so a new
# family compiles and validates as generated; the fragment's own docstring
# tells the author to replace this with the family's real story.
_CLOUD_SHAPE: dict[str, tuple[str, str, str, str]] = {
    "aws": ("ACCOUNT", "an AWS account", "S3_BUCKET", "an S3 bucket"),
    "azure": (
        "AZURE_SUBSCRIPTION",
        "an Azure subscription",
        "AZURE_STORAGE_CONTAINER",
        "a storage container",
    ),
    "gcp": ("GCP_PROJECT", "a GCP project", "GCP_STORAGE_BUCKET", "a storage bucket"),
    "k8s": ("K8S_CLUSTER", "a Kubernetes cluster", "K8S_POD", "a pod"),
}


def _class_name(scenario_type: str) -> str:
    return "".join(part.capitalize() for part in scenario_type.split("_"))


def _fragment_source(scenario_type: str, cloud: str, title: str) -> str:
    class_name = _class_name(scenario_type)
    entry_type, entry_desc, resource_type, resource_desc = _CLOUD_SHAPE[cloud]
    return f'''"""``core.{scenario_type}``: {title}.

Story: {entry_desc} exposes {resource_desc} that is reachable from outside
its own boundary and holds a sensitive data set. That direct exposure is the
critical risk this family teaches. Replace this story, the node/edge shape in
``_nodes``/``_edges``, and the finding in ``_findings`` with the family's real
attack; see the "Adding a Family" wiki page for a worked example.
"""

from __future__ import annotations

from random import Random
from typing import Any

from app.cloudforge.generate.fragments._core import Kit
from app.cloudforge.generate.fragments.base import FragmentBundle, register_core
from app.cloudforge.models.findings import (
    ExpectedFinding,
    FindingFamily,
    GroundTruthPath,
    SinkKind,
)
from app.cloudforge.models.graph import EdgeType, GraphEdge, GraphNode, NodeTags, NodeType

_TAGS = NodeTags(env="prod", owner="platform-team", app="{scenario_type}")
_ENTRY = "entry"
_RESOURCE = "resource"
_SINK = "sensitive-data"


@register_core
class {class_name}:
    scenario_type = "{scenario_type}"
    cloud = "{cloud}"
    prompt = (
        "{title}. Can it be reached from outside the boundary, and what "
        "sensitive data does it hold?"
    )
    checklist = ("{scenario_type}", "{title}")
    teaching_point = "{title}"

    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        kit = Kit(ns, _TAGS)
        return FragmentBundle(
            nodes=_nodes(kit), edges=_edges(kit), findings=_findings(kit), paths=[_critical(kit)]
        )


def _nodes(kit: Kit) -> list[GraphNode]:
    return [
        kit.node(_ENTRY, NodeType.{entry_type}, "entry", "high"),
        kit.node(_RESOURCE, NodeType.{resource_type}, "exposed-resource", "critical",
                  public_access="enabled"),
        kit.node(_SINK, NodeType.DATASET, "sensitive-records", "critical",
                  classification="restricted"),
    ]


def _edges(kit: Kit) -> list[GraphEdge]:
    return [
        kit.edge(_ENTRY, _RESOURCE, EdgeType.EXPOSED_TO_INTERNET, "critical"),
        kit.edge(_RESOURCE, _SINK, EdgeType.STORES_SENSITIVE_DATA, "critical"),
    ]


def _critical(kit: Kit) -> GroundTruthPath:
    return GroundTruthPath(
        id=kit.nid("path-critical-01"),
        severity="critical",
        nodes=[kit.nid(_ENTRY), kit.nid(_RESOURCE), kit.nid(_SINK)],
        edges=[
            kit.ek(_ENTRY, EdgeType.EXPOSED_TO_INTERNET, _RESOURCE),
            kit.ek(_RESOURCE, EdgeType.STORES_SENSITIVE_DATA, _SINK),
        ],
        sink_kind=SinkKind.DATA,
        target=kit.nid(_SINK),
        explanation=(
            "{title}: the exposed resource is reachable from outside the "
            "boundary with no compensating control, so it is reachable directly "
            "-> read of the sensitive data set it stores."
        ),
    )


def _findings(kit: Kit) -> list[ExpectedFinding]:
    return [
        ExpectedFinding(
            id=kit.nid("find-{scenario_type}-01"),
            severity="critical",
            family=FindingFamily.S3_PUBLIC_EXPOSURE,
            resource_ids=[kit.nid(_RESOURCE), kit.nid(_SINK)],
            expected_scanner_visibility="visible",
            ground_truth="The exposed resource allows public access and stores sensitive data.",
            remediation="Remove the public access grant and add a compensating control.",
        )
    ]
'''


def _example_source(scenario_type: str, cloud: str, title: str) -> str:
    return f"""cloud: {cloud}
scenario_type: {scenario_type}
environment: staging
difficulty: medium
company_profile:
  type: b2b_saas
  size: small
  app_name: {scenario_type.replace("_", "-")}
requirements:
  critical_chains: 1
  medium_findings: 0
  false_positives: 0
constraints:
  no_real_secrets: true
  no_destructive_permissions: true
  max_resources: 40
  deployable: false
"""


class ScaffoldError(Exception):
    """A ``new-family`` argument or target path is invalid."""


def new_family(scenario_type: str, cloud: str, title: str, root: Path) -> tuple[Path, Path]:
    """Write the fragment module and example spec for ``scenario_type``.

    Refuses to overwrite either file. Returns the two paths written.
    """
    if not _VALID_SCENARIO_TYPE.match(scenario_type):
        raise ScaffoldError(
            f"scenario_type {scenario_type!r} must be lower_snake_case, starting with a letter"
        )
    if cloud not in _CLOUDS:
        raise ScaffoldError(f"cloud {cloud!r} must be one of {', '.join(_CLOUDS)}")
    if not title.strip():
        raise ScaffoldError("--title must not be empty")

    fragment_path = (
        root / "app" / "cloudforge" / "generate" / "fragments" / f"core_{scenario_type}.py"
    )
    example_path = root / "examples" / f"{scenario_type}.yaml"
    for path in (fragment_path, example_path):
        if path.exists():
            raise ScaffoldError(f"refusing to overwrite existing file: {path}")

    fragment_path.parent.mkdir(parents=True, exist_ok=True)
    example_path.parent.mkdir(parents=True, exist_ok=True)
    fragment_path.write_text(_fragment_source(scenario_type, cloud, title), encoding="utf-8")
    example_path.write_text(_example_source(scenario_type, cloud, title), encoding="utf-8")
    return fragment_path, example_path
