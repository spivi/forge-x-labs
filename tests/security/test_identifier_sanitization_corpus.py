"""Adversarial resource-LABEL corpus (FXL-N2, regression-locks FXL-39).

The resource-LABEL position — ``resource "type" "<label>"`` — is a bare Terraform
identifier, not a quotable string, so :func:`hcl_str` cannot guard it. Every ``node.id``
is mapped through :func:`resource_name`, which must ALWAYS yield a Terraform-legal
identifier (``^[A-Za-z_][A-Za-z0-9_]*$``) so a hostile id can never break out of the
label position and inject a new block.

This module applies the shared :data:`HOSTILE_VALUES` corpus to ``node.id`` and asserts:

1. ``resource_name`` output always matches the legal-identifier regex.
2. No injected ``resource`` block (or the raw payload) appears in the emitted HCL —
   the label is the sanitized identifier, never the raw id.
3. A scenario carrying every hostile id across every labeled resource kind still
   ``terraform validate``s Success (one bounded invocation).
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from app.cloudforge.generate import ci_cd_iam_chain
from app.cloudforge.models.graph import (
    GraphNode,
    NodeSecurity,
    NodeTags,
    NodeType,
    ScenarioGraph,
)
from app.cloudforge.pipeline.terraform_emitter import TerraformEmitter
from app.cloudforge.pipeline.terraform_resource_blocks import resource_name
from tests.security.conftest import HOSTILE_VALUES, HostileValue

_TERRAFORM = shutil.which("terraform")

# A Terraform label starts with a letter/underscore, then letters/digits/underscores.
_TF_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_TAGS = NodeTags(env="staging", owner="platform-team", app="analytics-exporter")


def _node_with_id(node_id: str, node_type: NodeType = NodeType.S3_BUCKET) -> GraphNode:
    return GraphNode(
        id=node_id,
        type=node_type,
        name="safe-static-name",
        tags=_TAGS,
        security=NodeSecurity(criticality="low"),
        attributes={},
    )


# --- 1. resource_name is ALWAYS a legal identifier ----------------------------


def test_resource_name_is_always_a_legal_identifier(hostile: HostileValue) -> None:
    """Every corpus value as a ``node.id`` sanitizes to a legal Terraform label."""
    label = resource_name(_node_with_id(hostile.value))
    assert _TF_IDENTIFIER.match(
        label
    ), f"illegal identifier {label!r} from id {hostile.id!r} ({hostile.value!r})"


def test_resource_name_never_starts_with_a_digit(hostile: HostileValue) -> None:
    """A leading digit is guarded (Terraform labels may not start with a digit)."""
    label = resource_name(_node_with_id(hostile.value))
    assert not label[0].isdigit(), f"label starts with a digit: {label!r}"


def test_resource_name_is_never_empty(hostile: HostileValue) -> None:
    """Even the empty-string id maps to a non-empty legal label (``_``)."""
    assert resource_name(_node_with_id(hostile.value)), hostile.id


def test_resource_name_has_no_label_breakout_chars(hostile: HostileValue) -> None:
    """No quote / brace / whitespace survives into the label (would break the block)."""
    label = resource_name(_node_with_id(hostile.value))
    for forbidden in ('"', "{", "}", " ", "\n", "\t", "$", "%", "\x00"):
        assert forbidden not in label, f"{forbidden!r} leaked into label {label!r}"


# --- 2. no injected block appears in emitted HCL ------------------------------


def _hostile_id_graph(node_id: str) -> ScenarioGraph:
    """The ci_cd graph plus one bucket whose *id* carries a label-breakout payload."""
    base = ci_cd_iam_chain.build_graph()
    return ScenarioGraph(nodes=[*base.nodes, _node_with_id(node_id)], edges=base.edges)


def test_hostile_id_injects_no_resource_block(hostile: HostileValue, tmp_path: Path) -> None:
    """A hostile ``node.id`` never creates an extra ``resource`` block."""
    TerraformEmitter(_hostile_id_graph(hostile.value)).emit(tmp_path)
    s3 = (tmp_path / "s3.tf").read_text(encoding="utf-8")

    # The ci_cd family has exactly 2 real buckets; +1 hostile = 3, never more.
    assert s3.count('resource "aws_s3_bucket" "') == 3, hostile.id
    # No PWNED / injected label breaks out of the resource-LABEL position.
    assert '"PWNED"' not in s3
    assert 'resource "aws_iam_role" "PWNED"' not in s3
    # The emitted label is exactly the sanitized identifier.
    expected = resource_name(_node_with_id(hostile.value))
    assert f'resource "aws_s3_bucket" "{expected}"' in s3


# --- 3. one bounded terraform validate over every hostile id ------------------


def _every_hostile_id_graph() -> ScenarioGraph:
    """One graph giving every corpus value a hostile id across each labeled kind.

    ``resource_name`` is per-node, so different raw ids can collapse to the same
    sanitized label (a documented FXL-N4 collision surface). To keep this a pure
    *sanitization* test (not a collision test), we prefix each id with a unique safe
    stem so labels stay distinct while the hostile suffix still exercises the sink.
    """
    nodes: list[GraphNode] = []
    for idx, entry in enumerate(HOSTILE_VALUES):
        stem = f"id{idx}_"
        nodes.append(_node_with_id(stem + entry.value, NodeType.S3_BUCKET))
        nodes.append(_node_with_id(stem + entry.value, NodeType.IAM_ROLE))
        nodes.append(_node_with_id(stem + entry.value, NodeType.VPC))
    return ScenarioGraph(nodes=nodes, edges=[])


def test_every_hostile_id_is_terraform_valid(tmp_path: Path) -> None:
    """Every hostile id across every labeled kind still ``terraform validate``s."""
    if _TERRAFORM is None:  # pragma: no cover - terraform is on PATH in CI/dev
        return
    TerraformEmitter(_every_hostile_id_graph()).emit(tmp_path)
    subprocess.run(  # noqa: S603 — fixed argv, no shell, terraform from PATH
        ["terraform", "init", "-backend=false", "-input=false"],  # noqa: S607
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    result = subprocess.run(  # noqa: S603
        ["terraform", "validate"],  # noqa: S607
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


# --- 4. explicit FXL-39 regression-lock ---------------------------------------


def test_benign_hyphen_id_maps_to_underscore() -> None:
    """Preserve the pre-FXL-39 behavior for the common, benign case."""
    assert resource_name(_node_with_id("deploy-role-1")) == "deploy_role_1"


def test_label_breakout_id_is_fully_sanitized() -> None:
    """The FXL-39 breakout id collapses every illegal char to ``_`` (regression-lock)."""
    label = resource_name(_node_with_id('a" { evil }" { injected'))
    assert label == "a____evil______injected"
    assert _TF_IDENTIFIER.match(label)
