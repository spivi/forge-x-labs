"""Terraform emitter tests: the emitter is graph-driven (FXL-31).

Each scenario family must emit HCL for ITS OWN resources, rendered from the
scenario graph nodes — not a single hardcoded family. The regression suite pins
``ci_cd_iam_chain``'s resources; the per-family suite asserts
``public_data_exposure`` emits its public bucket and no PassRole chain.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from app.cloudforge import constants
from app.cloudforge.errors import GraphIntegrityError
from app.cloudforge.generate import ci_cd_iam_chain, public_data_exposure
from app.cloudforge.models.graph import (
    GraphNode,
    NodeSecurity,
    NodeTags,
    NodeType,
    ScenarioGraph,
)
from app.cloudforge.pipeline.terraform_blocks import derive_common_tags
from app.cloudforge.pipeline.terraform_emitter import TerraformEmitter
from app.cloudforge.pipeline.terraform_resource_blocks import resource_name

# A Terraform label must start with a letter/underscore, then letters/digits/underscores.
_TF_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _emit(graph: ScenarioGraph, tmp_path: Path) -> dict[str, str]:
    """Emit and return {filename: text} for every written ``.tf`` file."""
    written = TerraformEmitter(graph).emit(tmp_path)
    return {p.name: p.read_text(encoding="utf-8") for p in written}


def _blob(tf_files: dict[str, str]) -> str:
    return "\n".join(tf_files.values())


# --- output-tree contract ----------------------------------------------------


def test_emit_writes_all_six_tf_files(tmp_path: Path) -> None:
    written = TerraformEmitter(ci_cd_iam_chain.build_graph()).emit(tmp_path)

    names = {p.name for p in written}
    assert names == set(constants.TERRAFORM_FILES)


# --- ci_cd_iam_chain regression ----------------------------------------------


def test_ci_cd_iam_tf_has_full_passrole_chain(tmp_path: Path) -> None:
    files = _emit(ci_cd_iam_chain.build_graph(), tmp_path)
    iam = files["iam.tf"]

    assert "DeployRole" in iam
    assert "RuntimeRole" in iam
    assert "iam:PassRole" in iam
    assert "s3:Get*" in iam and "s3:List*" in iam


def test_ci_cd_s3_tf_has_both_buckets(tmp_path: Path) -> None:
    files = _emit(ci_cd_iam_chain.build_graph(), tmp_path)
    s3 = files["s3.tf"]

    assert "customer-exports" in s3
    assert "public-assets" in s3
    # The public-assets bucket carries a compensating control -> a bucket policy.
    assert "aws_s3_bucket_policy" in s3


def test_ci_cd_network_tf_has_open_ingress(tmp_path: Path) -> None:
    files = _emit(ci_cd_iam_chain.build_graph(), tmp_path)
    network = files["network.tf"]

    assert "aws_vpc" in network
    assert "aws_subnet" in network
    assert "0.0.0.0/0" in network


def test_ci_cd_hcl_has_no_forbidden_actions(tmp_path: Path) -> None:
    blob = _blob(_emit(ci_cd_iam_chain.build_graph(), tmp_path))

    for forbidden in constants.FORBIDDEN_PERMISSION_PATTERNS:
        stem = forbidden.split("*")[0]
        assert stem not in blob, f"forbidden action leaked into HCL: {forbidden}"


# --- public_data_exposure per-family ----------------------------------------


def test_pde_s3_tf_names_its_public_bucket(tmp_path: Path) -> None:
    files = _emit(public_data_exposure.build_graph(), tmp_path)
    s3 = files["s3.tf"]

    assert "customer-pii" in s3
    assert "public-looking-backups" in s3
    # It must NOT carry the ci_cd family's buckets.
    assert "customer-exports" not in s3


def test_pde_iam_tf_has_no_passrole_chain(tmp_path: Path) -> None:
    files = _emit(public_data_exposure.build_graph(), tmp_path)
    iam = files["iam.tf"]

    assert "iam:PassRole" not in iam
    assert "DeployRole" not in iam
    assert "RuntimeRole" not in iam


def test_pde_network_tf_is_valid_without_sg(tmp_path: Path) -> None:
    # public_data_exposure has a VPC but no Subnet / SecurityGroup nodes.
    files = _emit(public_data_exposure.build_graph(), tmp_path)
    network = files["network.tf"]

    assert "aws_vpc" in network
    assert "0.0.0.0/0" not in network


def test_pde_hcl_has_no_forbidden_actions(tmp_path: Path) -> None:
    blob = _blob(_emit(public_data_exposure.build_graph(), tmp_path))

    for forbidden in constants.FORBIDDEN_PERMISSION_PATTERNS:
        stem = forbidden.split("*")[0]
        assert stem not in blob


# --- static files are family-independent ------------------------------------


def test_static_files_carry_dummy_account_id(tmp_path: Path) -> None:
    files = _emit(public_data_exposure.build_graph(), tmp_path)

    assert constants.DUMMY_ACCOUNT_ID in files["main.tf"]
    assert constants.DUMMY_ACCOUNT_ID in files["variables.tf"]


# --- per-family common_tags are graph-derived (FXL-35) -----------------------


def test_main_tf_common_tags_match_pde_graph(tmp_path: Path) -> None:
    files = _emit(public_data_exposure.build_graph(), tmp_path)
    main = files["main.tf"]

    assert 'env   = "prod"' in main
    assert 'app   = "customer-data-lake"' in main
    assert 'owner = "data-platform-team"' in main
    # It must NOT carry the ci_cd family's hardcoded tags.
    assert "staging" not in main
    assert "analytics-exporter" not in main


def test_main_tf_common_tags_match_ci_cd_graph(tmp_path: Path) -> None:
    files = _emit(ci_cd_iam_chain.build_graph(), tmp_path)
    main = files["main.tf"]

    assert 'env   = "staging"' in main
    assert 'app   = "analytics-exporter"' in main
    assert 'owner = "platform-team"' in main
    assert "prod" not in main


# --- HCL escaping: a hostile node value must not break out (FXL-35) ----------


def _hostile_ci_cd_graph(payload: str) -> ScenarioGraph:
    """The ci_cd graph with one extra bucket whose name carries an attack payload."""
    graph = ci_cd_iam_chain.build_graph()
    hostile = GraphNode(
        id="s3-hostile",
        type=NodeType.S3_BUCKET,
        name=payload,
        tags=NodeTags(env="staging", owner="platform-team", app="analytics-exporter"),
        security=NodeSecurity(criticality="low"),
        attributes={},
    )
    return ScenarioGraph(nodes=[*graph.nodes, hostile], edges=graph.edges)


_BREAKOUT_PAYLOAD = 'pwned"\n}\nresource "aws_iam_role" "injected" {\n  name = "x'


def test_hostile_bucket_name_does_not_inject_new_resource(tmp_path: Path) -> None:
    files = _emit(_hostile_ci_cd_graph(_BREAKOUT_PAYLOAD), tmp_path)
    s3 = files["s3.tf"]

    # The injected role block must NOT appear as a real HCL statement.
    assert 'resource "aws_iam_role" "injected"' not in s3
    # The exact bucket count is unchanged (3 bucket resources: 2 real + 1 hostile).
    assert s3.count('resource "aws_s3_bucket" "') == 3
    # The payload survives only inside a single escaped string literal.
    assert "injected" in s3


def test_hostile_hcl_is_terraform_valid(tmp_path: Path) -> None:
    files = _emit(_hostile_ci_cd_graph(_BREAKOUT_PAYLOAD), tmp_path)
    s3 = files["s3.tf"]

    # A double-quote in the name is backslash-escaped inside the literal, never bare.
    assert '\\"' in s3
    # A newline in the name is escaped, so it cannot start a new HCL line.
    assert 'pwned"\n}\nresource' not in s3


# --- HCL interpolation ${...} / template %{...} must be neutralized (FXL-35) --


def test_interpolation_payload_is_inert(tmp_path: Path) -> None:
    # ``${...}`` is live interpolation in a double-quoted HCL string, not literal text.
    files = _emit(_hostile_ci_cd_graph("x${local.fake_account_id}"), tmp_path)
    s3 = files["s3.tf"]

    # The opener is neutralized to the HCL literal-escape ``$${`` — no live ``${`` left.
    assert "$${local.fake_account_id}" in s3
    assert "${local.fake_account_id}" not in s3.replace("$${local.fake_account_id}", "")


def test_template_directive_payload_is_inert(tmp_path: Path) -> None:
    # ``%{...}`` is a live HCL template directive; it must be neutralized to ``%%{``.
    payload = "%{ for x in [1,2] }${x}%{ endfor }"
    files = _emit(_hostile_ci_cd_graph(payload), tmp_path)
    s3 = files["s3.tf"]

    assert "%%{ for x in [1,2] }$${x}%%{ endfor }" in s3
    # No live template opener or interpolation opener survives.
    inert = s3.replace("$$", "").replace("%%", "")
    assert "${" not in inert
    assert "%{" not in inert


def test_interpolation_reference_does_not_break_validate(tmp_path: Path) -> None:
    # A ``${data.nonexistent...}`` name would fail ``terraform validate`` if it were
    # live (undeclared reference). Escaped, it is inert text and must NOT appear live.
    payload = "${data.nonexistent.thing.value}"
    files = _emit(_hostile_ci_cd_graph(payload), tmp_path)
    s3 = files["s3.tf"]

    assert "$${data.nonexistent.thing.value}" in s3
    # No LIVE ``${`` opener survives (strip the escaped ``$$`` first — ``${`` is a
    # substring of the inert ``$${``, so a bare ``not in`` would false-positive).
    assert "${" not in s3.replace("$$", "")
    _assert_terraform_validates(files, tmp_path)


# --- resource-LABEL injection: node.id must be sanitized to a legal id (FXL-39) --


_HOSTILE_IDS = ('a" { evil }', "123start", "", "x\ny", "a b-c", 'a" { evil }" {')


def test_resource_name_is_always_a_legal_identifier() -> None:
    for hostile in _HOSTILE_IDS:
        node = _node_with_id(hostile)
        assert _TF_IDENTIFIER.match(resource_name(node)), f"illegal id from {hostile!r}"


def test_resource_name_maps_hyphen_to_underscore() -> None:
    # Preserve the pre-FXL-39 behavior for the common, benign case.
    assert resource_name(_node_with_id("deploy-role-1")) == "deploy_role_1"


def _node_with_id(node_id: str) -> GraphNode:
    return GraphNode(
        id=node_id,
        type=NodeType.S3_BUCKET,
        name="hostile-id-bucket",
        tags=NodeTags(env="staging", owner="platform-team", app="analytics-exporter"),
        security=NodeSecurity(criticality="low"),
        attributes={},
    )


def _hostile_id_ci_cd_graph(node_id: str) -> ScenarioGraph:
    """The ci_cd graph plus one extra bucket whose *id* carries a label-breakout payload."""
    graph = ci_cd_iam_chain.build_graph()
    return ScenarioGraph(nodes=[*graph.nodes, _node_with_id(node_id)], edges=graph.edges)


def test_hostile_id_does_not_inject_new_block(tmp_path: Path) -> None:
    # An id crafted to break out of the resource-LABEL position must not create a block.
    files = _emit(_hostile_id_ci_cd_graph('a" { evil }" { injected'), tmp_path)
    s3 = files["s3.tf"]

    # Still exactly 3 bucket resources (2 real + 1 hostile) — no injected extra block.
    assert s3.count('resource "aws_s3_bucket" "') == 3
    # The emitted label is the sanitized identifier (every non-[A-Za-z0-9_] -> ``_``),
    # never the raw payload — so no breakout `{ evil }`/`{ injected` block is created.
    expected_label = resource_name(_node_with_id('a" { evil }" { injected'))
    assert expected_label == "a____evil______injected"
    assert f'resource "aws_s3_bucket" "{expected_label}"' in s3
    assert 'resource "aws_s3_bucket" "a"' not in s3


def test_hostile_id_hcl_is_terraform_valid(tmp_path: Path) -> None:
    files = _emit(_hostile_id_ci_cd_graph('a" { evil }\nbad'), tmp_path)
    _assert_terraform_validates(files, tmp_path)


# --- derive_common_tags is total on an empty graph (FXL-39) ------------------


def test_derive_common_tags_on_empty_graph_does_not_raise() -> None:
    tags = derive_common_tags([])

    assert isinstance(tags, NodeTags)
    assert tags == NodeTags(env="unknown", owner="unknown", app="unknown")


# --- per-type label-collision detection: distinct ids must not collide (FXL-N4) --


def _node(node_id: str, node_type: NodeType, name: str = "n") -> GraphNode:
    return GraphNode(
        id=node_id,
        type=node_type,
        name=name,
        tags=NodeTags(env="staging", owner="platform-team", app="analytics-exporter"),
        security=NodeSecurity(criticality="low"),
        attributes={},
    )


def test_colliding_ids_same_type_raise_graph_integrity_error(tmp_path: Path) -> None:
    # ``a-b`` and ``a_b`` both sanitize to the label ``a_b`` — Terraform would then
    # error on a duplicate ``aws_s3_bucket`` label. Reject BEFORE emission instead.
    graph = ScenarioGraph(
        nodes=[_node("a-b", NodeType.S3_BUCKET), _node("a_b", NodeType.S3_BUCKET)],
        edges=[],
    )

    with pytest.raises(GraphIntegrityError) as excinfo:
        TerraformEmitter(graph).emit(tmp_path)

    message = str(excinfo.value)
    # The error must name BOTH colliding node ids and the shared label.
    assert "a-b" in message
    assert "a_b" in message
    assert resource_name(_node("a-b", NodeType.S3_BUCKET)) in message


def test_colliding_ids_rejected_before_any_file_is_written(tmp_path: Path) -> None:
    graph = ScenarioGraph(
        nodes=[_node("a-b", NodeType.S3_BUCKET), _node("a_b", NodeType.S3_BUCKET)],
        edges=[],
    )

    with pytest.raises(GraphIntegrityError):
        TerraformEmitter(graph).emit(tmp_path)

    # Fail loud, fail early: no partial ``.tf`` tree is left behind.
    assert list(tmp_path.iterdir()) == []


def test_colliding_labels_across_different_types_do_not_collide(tmp_path: Path) -> None:
    # Terraform labels are namespaced by resource TYPE, so ``a_b`` as an
    # ``aws_s3_bucket`` label and ``a_b`` as an ``aws_iam_role`` label never clash.
    graph = ScenarioGraph(
        nodes=[_node("a-b", NodeType.S3_BUCKET), _node("a_b", NodeType.IAM_ROLE)],
        edges=[],
    )

    written = TerraformEmitter(graph).emit(tmp_path)

    assert {p.name for p in written} == set(constants.TERRAFORM_FILES)


def test_non_emitting_node_types_never_trigger_a_collision(tmp_path: Path) -> None:
    # ACCOUNT / CICDIdentity / Application / DataSet / LogTrail emit NO resource,
    # so ids that would sanitize to the same label carry no Terraform label to clash.
    graph = ScenarioGraph(
        nodes=[_node("a-b", NodeType.ACCOUNT), _node("a_b", NodeType.CICD_IDENTITY)],
        edges=[],
    )

    written = TerraformEmitter(graph).emit(tmp_path)

    assert {p.name for p in written} == set(constants.TERRAFORM_FILES)


def test_shipped_families_emit_without_false_positive_collision(tmp_path: Path) -> None:
    # Zero collisions today: both real families must still emit all six files.
    for build_graph in (ci_cd_iam_chain.build_graph, public_data_exposure.build_graph):
        family_dir = tmp_path / build_graph.__module__.rsplit(".", 1)[-1]
        family_dir.mkdir()
        written = TerraformEmitter(build_graph()).emit(family_dir)
        assert {p.name for p in written} == set(constants.TERRAFORM_FILES)


def _assert_terraform_validates(files: dict[str, str], tmp_path: Path) -> None:
    """Run real ``terraform validate`` on the emitted tree when terraform is on PATH."""
    if shutil.which("terraform") is None:
        return
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
