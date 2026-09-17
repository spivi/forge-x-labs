"""A student estate is padded with its own vendor's resources.

For every example spec at two seeds: the stripped estate carries only the node
types its ``cloud`` allows, every one of those types has a workbench zone to sit
in (parsed from ``NETWORK_ZONES`` in the template, so the page never drops a
resource on the floor), and the Terraform emitter writes a real file for every
vendor present and the empty header for every vendor absent.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.cloudforge import constants
from app.cloudforge.generate.composer import GraphComposer
from app.cloudforge.io.loaders import load_yaml
from app.cloudforge.lab.strip import strip_graph
from app.cloudforge.models.scenario import ScenarioSpec
from app.cloudforge.pipeline.terraform_emitter import TerraformEmitter

_EXAMPLES = sorted(Path("examples").glob("*.yaml"))
_SEEDS = (0, 17)
_CASES = [
    pytest.param(example, seed, id=f"{example.stem}-{seed}")
    for example in _EXAMPLES
    for seed in _SEEDS
]
_TEMPLATE = Path("app/cloudforge/lab/estate_template.html")
_ZONES_BLOCK = re.compile(r"const NETWORK_ZONES = \[(.*?)\n\];", re.DOTALL)
_ZONE_TYPES = re.compile(r"types:\s*\[(.*?)\]", re.DOTALL)
_VENDOR_PREFIXES = {"azure": "Azure", "gcp": "Gcp", "k8s": "K8s"}
_VENDOR_FILES = {"azure": "azure.tf", "gcp": "gcp.tf", "k8s": "k8s.tf"}
# ``DataSet`` is the generic labeled-data type every pool mints and the Azure and
# GCP paths end on, whatever the cloud; it is not a vendor type.
_GENERIC_SINK = "DataSet"


def _zoned_types() -> set[str]:
    block = _ZONES_BLOCK.search(_TEMPLATE.read_text(encoding="utf-8"))
    assert block, "NETWORK_ZONES not found in estate_template.html"
    types: set[str] = set()
    for group in _ZONE_TYPES.findall(block.group(1)):
        types |= set(json.loads(f"[{group}]"))
    return types


def _estate(example: Path, seed: int) -> tuple[ScenarioSpec, list[str]]:
    spec = ScenarioSpec.model_validate(load_yaml(example))
    graph = GraphComposer(spec, seed=seed).generate().graph
    return spec, [str(n["type"]) for n in strip_graph(graph)["nodes"]]


def _is_vendor_type(node_type: str) -> bool:
    return node_type.startswith(tuple(_VENDOR_PREFIXES.values()))


def test_the_examples_cover_every_vendor() -> None:
    clouds = {ScenarioSpec.model_validate(load_yaml(e)).cloud for e in _EXAMPLES}
    assert {"aws", "azure", "gcp", "k8s"} <= clouds


@pytest.mark.parametrize(("example", "seed"), _CASES)
def test_student_estate_types_are_all_from_the_vendors_allowed_set(
    example: Path, seed: int
) -> None:
    spec, types = _estate(example, seed)
    if spec.cloud in ("azure", "gcp"):
        prefix = _VENDOR_PREFIXES[spec.cloud]
        for node_type in types:
            assert node_type.startswith(prefix) or node_type == _GENERIC_SINK, node_type
    elif spec.cloud == "k8s":
        for node_type in types:
            assert not node_type.startswith(("Azure", "Gcp")), node_type
        assert any(t.startswith("K8s") for t in types)
    else:
        assert spec.cloud == "aws"
        for node_type in types:
            assert not _is_vendor_type(node_type), node_type


@pytest.mark.parametrize(("example", "seed"), _CASES)
def test_every_node_type_in_the_estate_has_a_workbench_zone(example: Path, seed: int) -> None:
    zoned = _zoned_types()
    _spec, types = _estate(example, seed)
    missing = set(types) - zoned
    assert not missing, sorted(missing)


@pytest.mark.parametrize(("example", "seed"), _CASES)
def test_emitter_writes_a_file_for_every_vendor_present(
    tmp_path: Path, example: Path, seed: int
) -> None:
    spec = ScenarioSpec.model_validate(load_yaml(example))
    graph = GraphComposer(spec, seed=seed).generate().graph
    paths = TerraformEmitter(graph).emit(tmp_path)
    written = {p.name: p.read_text(encoding="utf-8") for p in paths}
    present = {
        vendor
        for vendor, prefix in _VENDOR_PREFIXES.items()
        if any(n.type.value.startswith(prefix) for n in graph.nodes)
    }
    for vendor, filename in _VENDOR_FILES.items():
        text = written[filename]
        if vendor in present:
            assert text != constants.EMPTY_TF_HEADER, (vendor, filename)
            assert "resource " in text, (vendor, filename)
        else:
            assert text == constants.EMPTY_TF_HEADER, (vendor, filename)
    assert 'provider "aws"' in written["providers.tf"]
    assert ('provider "azurerm"' in written["providers.tf"]) == ("azure" in present)
    assert ('provider "google"' in written["providers.tf"]) == ("gcp" in present)
    assert ('provider "kubernetes"' in written["providers.tf"]) == ("k8s" in present)
