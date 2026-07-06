"""FXL-108 (FXL-STRESS-3): file-based adversarial HCL/resource-id corpus.

Extends the FXL-35/FXL-39 regression suite (``test_hcl_injection_corpus.py`` /
``test_identifier_sanitization_corpus.py``) with the STRESS-3 deliverable: a
hostile corpus that lives in ``tests/security/corpus/*.txt`` (audit-friendly, not
hardcoded Python), applied to every untrusted graph-field string sink, plus a
tool-backed (real ``terraform validate``) acceptance pass and explicit assertions
on the three stress-contract clauses this ticket targets:

* **S2** — no emitted artifact requires cloud credentials (dummy account, no apply
  path). Regression-checked here via the static provider file.
* **S3** — no unsafe interpolation (live ``${``/``%{``) and no duplicate resource
  label in emitted HCL.
* **S7** — no forbidden/destructive permission pattern survives into emitted HCL.

Also proves the file-write surface: every path the emitter writes is a fixed
filename constant under the caller-supplied scenario/terraform directory — a
hostile graph field can NEVER change *where* a file is written (no traversal via
node data), only what's inside it.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from app.cloudforge import constants
from app.cloudforge.errors import GraphIntegrityError
from app.cloudforge.generate import ci_cd_iam_chain
from app.cloudforge.models.graph import (
    GraphNode,
    NodeSecurity,
    NodeTags,
    NodeType,
    ScenarioGraph,
)
from app.cloudforge.pipeline.terraform_emitter import TerraformEmitter
from app.cloudforge.pipeline.terraform_resource_blocks import (
    bucket_block,
    policy_block,
    resource_name,
    role_block,
    security_group_block,
    vpc_block,
)
from tests.security.corpus_loader import load_hcl_strings, load_resource_ids, load_tag_values

_TERRAFORM = shutil.which("terraform")
_TF_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

HCL_STRINGS = load_hcl_strings()
RESOURCE_IDS = load_resource_ids()
TAG_VALUES = load_tag_values()


def _ids(values: list[str]) -> list[str]:
    """Stable, readable parametrize ids (index-prefixed; the raw value can be huge)."""
    return [f"{i}:{v[:24]!r}" for i, v in enumerate(values)]


# --- HCL semantics helper (mirrors test_hcl_injection_corpus.py) --------------


def _has_live_hcl_opener(rendered: str) -> bool:
    """True iff ``rendered`` contains a LIVE ``${``/``%{`` opener (S3).

    A lone marker char immediately before ``{`` is live; ``$$``/``%%`` (or more) is
    HCL's own escaped-literal form.
    """
    for match in re.finditer(r"([$%])\{", rendered):
        marker = match.group(1)
        i = match.start()
        preceding = 0
        while i - 1 >= 0 and rendered[i - 1] == marker:
            preceding += 1
            i -= 1
        if preceding == 0:
            return True
    return False


def _node(
    node_type: NodeType, *, node_id: str = "fixed_safe_id", name: str = "n", **attrs: str
) -> GraphNode:
    return GraphNode(
        id=node_id,
        type=node_type,
        name=name,
        tags=NodeTags(env="staging", owner="platform-team", app="analytics-exporter"),
        security=NodeSecurity(criticality="low"),
        attributes=dict(attrs),
    )


# --- 1. every hcl_strings.txt value, applied to every string sink -------------


@pytest.mark.parametrize("value", HCL_STRINGS, ids=_ids(HCL_STRINGS))
def test_sink_role_name_is_inert(value: str) -> None:
    block = role_block(_node(NodeType.IAM_ROLE, name=value))
    assert not _has_live_hcl_opener(block)
    assert 'resource "aws_iam_role" "PWNED"' not in block
    assert 'resource "aws_iam_policy" "evil"' not in block


@pytest.mark.parametrize("value", HCL_STRINGS, ids=_ids(HCL_STRINGS))
def test_sink_bucket_name_is_inert(value: str) -> None:
    block = bucket_block(_node(NodeType.S3_BUCKET, name=value))
    assert not _has_live_hcl_opener(block)
    assert 'resource "aws_iam_policy" "evil"' not in block


@pytest.mark.parametrize("value", HCL_STRINGS, ids=_ids(HCL_STRINGS))
def test_sink_bucket_policy_arn_is_inert(value: str) -> None:
    """The compensating-control bucket-policy sink embeds ``node.name`` via the arn."""
    block = bucket_block(_node(NodeType.S3_BUCKET, name=value, compensating_control="true"))
    assert "aws_s3_bucket_policy" in block, "compensating-control policy block did not emit"
    assert not _has_live_hcl_opener(block)


@pytest.mark.parametrize("value", HCL_STRINGS, ids=_ids(HCL_STRINGS))
def test_sink_security_group_name_is_inert(value: str) -> None:
    block = security_group_block(_node(NodeType.SECURITY_GROUP, name=value), "vpc_ref")
    assert not _has_live_hcl_opener(block)


@pytest.mark.parametrize("value", HCL_STRINGS, ids=_ids(HCL_STRINGS))
def test_sink_iam_policy_resource_arn_is_inert(value: str) -> None:
    block = policy_block(_node(NodeType.IAM_POLICY, resource=value))
    assert not _has_live_hcl_opener(block)


@pytest.mark.parametrize("value", HCL_STRINGS, ids=_ids(HCL_STRINGS))
def test_sink_vpc_cidr_is_inert(value: str) -> None:
    block = vpc_block(_node(NodeType.VPC, cidr=value))
    assert not _has_live_hcl_opener(block)


@pytest.mark.parametrize("value", HCL_STRINGS, ids=_ids(HCL_STRINGS))
def test_sink_ingress_cidr_is_inert(value: str) -> None:
    block = security_group_block(_node(NodeType.SECURITY_GROUP, ingress_cidr=value), "vpc_ref")
    assert not _has_live_hcl_opener(block)


# --- 2. the ``actions`` LIST-valued attribute sink (IAM policy statement) -----
#
# Every other sink is a scalar str attribute; ``actions`` is a ``list[str]`` reaching
# the SAME jsonencode-wrapped policy document via ``_actions()``. A list-valued sink
# is a structurally distinct code path (loop + json.dumps of a list, not a scalar) so
# it gets its own pass over the whole corpus rather than inheriting scalar coverage.


@pytest.mark.parametrize("value", HCL_STRINGS, ids=_ids(HCL_STRINGS))
def test_sink_iam_actions_list_is_inert(value: str) -> None:
    node = _node(NodeType.IAM_POLICY)
    node = node.model_copy(
        update={"attributes": {"actions": [value], "resource": "arn:aws:s3:::x"}}
    )
    block = policy_block(node)
    assert not _has_live_hcl_opener(block)
    assert 'resource "aws_iam_policy" "evil"' not in block


def test_iam_actions_list_multiple_hostile_entries_stays_inert() -> None:
    """A list carrying several corpus values at once (not just one) stays inert."""
    node = _node(NodeType.IAM_POLICY)
    node = node.model_copy(
        update={"attributes": {"actions": list(HCL_STRINGS[:10]), "resource": "arn:aws:s3:::x"}}
    )
    block = policy_block(node)
    assert not _has_live_hcl_opener(block)


# --- 3. every tag_values.txt value, applied to env/owner/app ------------------


def _tagged_graph(value: str) -> ScenarioGraph:
    base = ci_cd_iam_chain.build_graph()
    tainted = GraphNode(
        id="acct_tainted",
        type=NodeType.ACCOUNT,
        name="tainted-account",
        tags=NodeTags(env=value, owner=value, app=value),
        security=NodeSecurity(criticality="low"),
        attributes={},
    )
    return ScenarioGraph(nodes=[tainted, *base.nodes], edges=base.edges)


@pytest.mark.parametrize("value", TAG_VALUES, ids=_ids(TAG_VALUES))
def test_sink_tag_values_are_inert(value: str, tmp_path: Path) -> None:
    written = TerraformEmitter(_tagged_graph(value)).emit(tmp_path)
    main = (tmp_path / "main.tf").read_text(encoding="utf-8")
    assert "main.tf" in {p.name for p in written}
    assert not _has_live_hcl_opener(main)


# --- 4. every resource_ids.txt value, applied to node.id (the LABEL surface) --


@pytest.mark.parametrize("value", RESOURCE_IDS, ids=_ids(RESOURCE_IDS))
def test_resource_name_is_always_a_legal_identifier(value: str) -> None:
    label = resource_name(_node(NodeType.S3_BUCKET, node_id=value))
    assert _TF_IDENTIFIER.match(label), f"illegal identifier {label!r} from id {value!r}"


@pytest.mark.parametrize("value", RESOURCE_IDS, ids=_ids(RESOURCE_IDS))
def test_hostile_id_injects_no_resource_block(value: str, tmp_path: Path) -> None:
    base = ci_cd_iam_chain.build_graph()
    graph = ScenarioGraph(
        nodes=[*base.nodes, _node(NodeType.S3_BUCKET, node_id=value)], edges=base.edges
    )
    TerraformEmitter(graph).emit(tmp_path)
    s3 = (tmp_path / "s3.tf").read_text(encoding="utf-8")

    assert s3.count('resource "aws_s3_bucket" "') == 3, value
    assert '"PWNED"' not in s3
    assert 'resource "aws_iam_role" "injected"' not in s3
    expected = resource_name(_node(NodeType.S3_BUCKET, node_id=value))
    assert f'resource "aws_s3_bucket" "{expected}"' in s3


# --- 5. D006 regression-lock: distinct hostile ids that COLLIDE are REJECTED --


def test_two_hostile_ids_colliding_after_sanitization_are_rejected(tmp_path: Path) -> None:
    """Two distinct corpus ids that sanitize to the SAME label must raise, not emit.

    e.g. ``"${local.x}"`` and ``"%{local.x}"`` are distinct ids but both collapse
    every non-identifier char to ``_`` — proving the pre-emission collision guard
    (D006 / label_collisions.check_label_collisions) still catches a HOSTILE-input
    collision, not just the benign hyphen/underscore case already regression-locked.
    """
    left = _node(NodeType.S3_BUCKET, node_id="${x}", name="left")
    right = _node(NodeType.S3_BUCKET, node_id="%{x}", name="right")
    assert resource_name(left) == resource_name(right), "test setup must produce a real collision"

    graph = ScenarioGraph(nodes=[left, right], edges=[])
    with pytest.raises(GraphIntegrityError):
        TerraformEmitter(graph).emit(tmp_path)
    # Fail loud, fail early: no partial `.tf` tree left behind.
    assert list(tmp_path.iterdir()) == []


# --- 6. S7 regression-lock: forbidden permissions never survive into HCL -----


def test_forbidden_permission_in_actions_is_rendered_but_still_a_string_literal(
    tmp_path: Path,
) -> None:
    """A forbidden action IS rendered (the emitter doesn't filter policy content —
    that is graph_risk's/validate's job per S7), but it can never escape its JSON
    string context to forge a *new*, unguarded statement or resource block.
    """
    for forbidden in constants.FORBIDDEN_PERMISSION_PATTERNS:
        node = _node(NodeType.IAM_POLICY)
        node = node.model_copy(
            update={"attributes": {"actions": [forbidden], "resource": "arn:aws:s3:::x"}}
        )
        block = policy_block(node)
        assert not _has_live_hcl_opener(block)
        # Exactly one resource block — no forbidden action can spawn a second one.
        assert block.count('resource "aws_iam_policy"') == 1


# --- 7. S2/emit-path containment: every write is a fixed filename constant ---


def test_emit_writes_only_the_fixed_filename_set(tmp_path: Path) -> None:
    """No hostile graph field can change WHERE a file is written.

    Every ``TerraformEmitter._write`` call target is ``terraform_dir / <constant
    filename>`` — filenames come from ``_STATIC_BUILDERS``/``_GRAPH_BUILDERS`` keys,
    never graph data. Assert the written set is EXACTLY the declared 6, even when
    graph fields are maximally hostile (path-traversal-shaped ids/names included).
    """
    base = ci_cd_iam_chain.build_graph()
    hostile_nodes = [
        _node(NodeType.S3_BUCKET, node_id="../../../etc/passwd", name="../../escape"),
        _node(NodeType.IAM_ROLE, node_id="..\\..\\windows\\escape", name="..\\..\\escape"),
    ]
    graph = ScenarioGraph(nodes=[*base.nodes, *hostile_nodes], edges=base.edges)
    written = TerraformEmitter(graph).emit(tmp_path)

    assert {p.name for p in written} == set(constants.TERRAFORM_FILES)
    # Every written path resolves INSIDE tmp_path — no traversal above the target dir.
    resolved_base = tmp_path.resolve()
    for path in written:
        assert path.resolve().is_relative_to(resolved_base), path
    # Nothing was written anywhere else under tmp_path's parent.
    assert {p.name for p in tmp_path.iterdir()} == set(constants.TERRAFORM_FILES)


def test_static_provider_file_has_no_real_credentials(tmp_path: Path) -> None:
    """S2 regression-lock: the emitted provider file skips real cloud credentials."""
    TerraformEmitter(ci_cd_iam_chain.build_graph()).emit(tmp_path)
    providers = (tmp_path / "providers.tf").read_text(encoding="utf-8")
    assert "skip_credentials_validation = true" in providers
    assert "skip_requesting_account_id  = true" in providers
    assert "mock_access_key" in providers
    assert "mock_secret_key" in providers


# --- 8. tool-backed: the WHOLE corpus, accepted, still terraform validate's ---


def _write_generic_locals(tmp_path: Path, values: list[str]) -> None:
    """Emit every value through the product's real ``hcl_str`` sink into a schema-free
    ``locals`` block — isolates pure HCL-injection safety from AWS content-schema
    rejection (a > 63-char bucket name etc. is a separate, also-acceptable outcome).
    """
    from app.cloudforge.pipeline.terraform_resource_blocks import hcl_str

    lines = ["locals {"]
    for idx, value in enumerate(values):
        lines.append(f"  v{idx} = {hcl_str(value)}")
    lines.append("}\n")
    (tmp_path / "corpus.tf").write_text("\n".join(lines), encoding="utf-8")


def _terraform_validate(tmp_path: Path) -> subprocess.CompletedProcess[str]:
    subprocess.run(  # noqa: S603 — fixed argv, no shell, terraform from PATH
        ["terraform", "init", "-backend=false", "-input=false"],  # noqa: S607
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    return subprocess.run(  # noqa: S603
        ["terraform", "validate", "-json"],  # noqa: S607
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )


@pytest.mark.integration
def test_whole_hcl_strings_corpus_is_terraform_valid(tmp_path: Path) -> None:
    """The entire ``hcl_strings.txt`` corpus, escaped via ``hcl_str``, validates clean."""
    if _TERRAFORM is None:
        pytest.skip("terraform not found on PATH")
    _write_generic_locals(tmp_path, HCL_STRINGS)
    result = _terraform_validate(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.integration
def test_whole_scenario_with_every_hostile_id_is_terraform_valid(tmp_path: Path) -> None:
    """One scenario giving every ``resource_ids.txt`` value a distinct-safe-stem id
    across every labeled resource kind still ``terraform validate``s Success.

    Distinct safe stems keep this a pure *sanitization* test (D006 collisions are
    covered separately, above) rather than accidentally exercising the collision
    guard here.
    """
    if _TERRAFORM is None:
        pytest.skip("terraform not found on PATH")
    nodes: list[GraphNode] = []
    for idx, value in enumerate(RESOURCE_IDS):
        stem = f"id{idx}_"
        nodes.append(_node(NodeType.S3_BUCKET, node_id=stem + value))
        nodes.append(_node(NodeType.IAM_ROLE, node_id=stem + value))
        nodes.append(_node(NodeType.VPC, node_id=stem + value))
    graph = ScenarioGraph(nodes=nodes, edges=[])

    TerraformEmitter(graph).emit(tmp_path)
    result = _terraform_validate(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.integration
def test_full_ci_cd_scenario_with_tag_corpus_is_terraform_valid(tmp_path: Path) -> None:
    """A full, real scenario family, its Account-node tags carrying a corpus value
    with the interpolation/breakout surface, still ``terraform validate``s Success
    end to end (the full emitter pipeline, not just the isolated ``hcl_str`` sink).

    ONE bounded ``terraform init`` (the AWS provider plugin download is heavy; the
    repo convention — see ``test_hcl_injection_corpus.py`` — is a single invocation
    per test, not one per corpus value). The representative value below carries the
    two live-interpolation surfaces (``${``/``%{``); the rest of ``tag_values.txt``
    is already proven inert (no terraform needed) by ``test_sink_tag_values_are_inert``
    and, combined into one schema-free tree, by
    ``test_parsed_validate_json_never_reports_error_for_accepted_corpus`` below.
    """
    if _TERRAFORM is None:
        pytest.skip("terraform not found on PATH")
    representative = "%{ if true }${local.fake_account_id}%{ endif }"
    TerraformEmitter(_tagged_graph(representative)).emit(tmp_path)
    result = _terraform_validate(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.integration
def test_parsed_validate_json_never_reports_error_for_accepted_corpus(tmp_path: Path) -> None:
    """Parse ``terraform validate -json``'s ``valid``/``error_count``/``diagnostics``
    explicitly (not just returncode) — the ticket's acceptance criteria requires
    inspecting the structured fields, not only the process exit status.
    """
    import json

    if _TERRAFORM is None:
        pytest.skip("terraform not found on PATH")
    _write_generic_locals(tmp_path, HCL_STRINGS + TAG_VALUES)
    result = _terraform_validate(tmp_path)
    payload = json.loads(result.stdout)
    assert payload["valid"] is True, payload
    assert payload["error_count"] == 0, payload
    assert payload["diagnostics"] == [], payload
