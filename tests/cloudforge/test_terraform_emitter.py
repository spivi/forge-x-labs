"""Terraform emitter tests: the emitter is graph-driven (FXL-31).

Each scenario family must emit HCL for ITS OWN resources, rendered from the
scenario graph nodes — not a single hardcoded family. The regression suite pins
``ci_cd_iam_chain``'s resources; the per-family suite asserts
``public_data_exposure`` emits its public bucket and no PassRole chain.
"""

from __future__ import annotations

from pathlib import Path

from app.cloudforge import constants
from app.cloudforge.generate import ci_cd_iam_chain, public_data_exposure
from app.cloudforge.models.graph import (
    GraphNode,
    NodeSecurity,
    NodeTags,
    NodeType,
    ScenarioGraph,
)
from app.cloudforge.pipeline.terraform_emitter import TerraformEmitter


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


def _hostile_ci_cd_graph() -> ScenarioGraph:
    """The ci_cd graph with one bucket's name carrying an HCL-breakout payload."""
    graph = ci_cd_iam_chain.build_graph()
    hostile = GraphNode(
        id="s3-hostile",
        type=NodeType.S3_BUCKET,
        name='pwned"\n}\nresource "aws_iam_role" "injected" {\n  name = "x',
        tags=NodeTags(env="staging", owner="platform-team", app="analytics-exporter"),
        security=NodeSecurity(criticality="low"),
        attributes={},
    )
    return ScenarioGraph(nodes=[*graph.nodes, hostile], edges=graph.edges)


def test_hostile_bucket_name_does_not_inject_new_resource(tmp_path: Path) -> None:
    files = _emit(_hostile_ci_cd_graph(), tmp_path)
    s3 = files["s3.tf"]

    # The injected role block must NOT appear as a real HCL statement.
    assert 'resource "aws_iam_role" "injected"' not in s3
    # The exact bucket count is unchanged (3 bucket resources: 2 real + 1 hostile).
    assert s3.count('resource "aws_s3_bucket" "') == 3
    # The payload survives only inside a single escaped string literal.
    assert "injected" in s3


def test_hostile_hcl_is_terraform_valid(tmp_path: Path) -> None:
    files = _emit(_hostile_ci_cd_graph(), tmp_path)
    s3 = files["s3.tf"]

    # A double-quote in the name is backslash-escaped inside the literal, never bare.
    assert '\\"' in s3
    # A newline in the name is escaped, so it cannot start a new HCL line.
    assert 'pwned"\n}\nresource' not in s3
