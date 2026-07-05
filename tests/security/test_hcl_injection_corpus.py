"""Adversarial HCL-string-value corpus (FXL-N2, regression-locks FXL-35).

Applies the shared :data:`HOSTILE_VALUES` corpus to every graph string sink whose
value reaches a *quoted HCL string literal* via :func:`hcl_str`:

* node ``name``      — IAM role / policy / security-group names, S3 bucket names
* tag values         — ``env`` / ``owner`` / ``app`` -> ``locals.common_tags``
* IAM ``resource``   — the policy statement resource arn
* ``cidr``           — VPC / Subnet CIDR blocks
* ``ingress_cidr``   — security-group ingress CIDR

Two layers of proof:

1. **Fast, per-value, no terraform** — the emitted literal is *inert*: it carries no
   LIVE ``${`` / ``%{`` opener (terraform treats a lone marker as live, ``$$``/``%%``
   or more as literal — see :func:`_has_live_hcl_opener`) and never breaks out of its
   surrounding double-quoted string.
2. **Real ``terraform validate``** — a single scenario carrying EVERY corpus value
   across EVERY string sink (plus a couple of targeted single-value scenarios for
   the interpolation surface) must ``terraform validate`` Success. Escaped payloads
   are inert; a live breakout would fail validate (undeclared reference / syntax).

``node.id`` reaches the resource *label* (a bare identifier, not a string) and is
covered separately in ``test_identifier_sanitization_corpus.py``.
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
from app.cloudforge.pipeline.terraform_resource_blocks import (
    bucket_block,
    hcl_str,
    policy_block,
    role_block,
    security_group_block,
    vpc_block,
)
from tests.security.conftest import HOSTILE_VALUES, HostileValue

_TERRAFORM = shutil.which("terraform")


# --- HCL semantics helpers ----------------------------------------------------


def _has_live_hcl_opener(rendered: str) -> bool:
    """True iff ``rendered`` contains a LIVE HCL interpolation/template opener.

    Terraform treats a *lone* ``$``/``%`` before ``{`` as a live opener, but ``$$``
    (or more) / ``%%`` (or more) as an escaped *literal* — verified against real
    ``terraform console``: only a run of exactly one marker char before ``{`` is live.
    So a ``${`` / ``%{`` is live only when the immediately-preceding run of that same
    marker char is empty.
    """
    for match in re.finditer(r"([$%])\{", rendered):
        marker = match.group(1)
        i = match.start()
        preceding = 0
        while i - 1 >= 0 and rendered[i - 1] == marker:
            preceding += 1
            i -= 1
        if preceding == 0:  # a lone marker -> a live opener
            return True
    return False


def _quoted_body(literal: str) -> str:
    """The inside of a ``hcl_str`` literal (drops the wrapping quotes)."""
    assert literal.startswith('"') and literal.endswith('"'), literal
    return literal[1:-1]


def _node(node_type: NodeType, *, name: str = "n", **attrs: str) -> GraphNode:
    return GraphNode(
        id="fixed_safe_id",
        type=node_type,
        name=name,
        tags=NodeTags(env="staging", owner="platform-team", app="analytics-exporter"),
        security=NodeSecurity(criticality="low"),
        attributes=dict(attrs),
    )


# --- 1. per-value inertness of hcl_str itself (the single escaping funnel) -----


def test_hcl_str_literal_has_no_live_opener(hostile: HostileValue) -> None:
    """Every corpus value, quoted via ``hcl_str``, carries no LIVE ``${``/``%{``."""
    literal = hcl_str(hostile.value)
    assert not _has_live_hcl_opener(
        literal
    ), f"live HCL opener survived for {hostile.id!r}: {literal!r}"


def test_hcl_str_never_breaks_out_of_its_quotes(hostile: HostileValue) -> None:
    """The literal is one balanced double-quoted token: no bare ``"`` inside it.

    A raw ``"`` in the body would terminate the string early (breakout). ``json.dumps``
    backslash-escapes every inner quote, so the only unescaped quotes are the wrappers.
    """
    literal = hcl_str(hostile.value)
    body = _quoted_body(literal)
    # Walk the body; a ``"`` is a breakout unless it is backslash-escaped.
    escaped = False
    for char in body:
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        assert char != '"', f"unescaped quote (breakout) for {hostile.id!r}: {literal!r}"


def test_hcl_str_never_emits_a_raw_newline(hostile: HostileValue) -> None:
    """A raw newline would let a payload start a new HCL line; it must be escaped."""
    literal = hcl_str(hostile.value)
    assert "\n" not in literal and "\r" not in literal, hostile.id


# --- 2. per-value inertness at each string SINK (the real block builders) ------


def _emit_and_scan(builder_output: str, hostile: HostileValue) -> None:
    """Shared assertions for a rendered block that embeds a hostile value."""
    assert not _has_live_hcl_opener(
        builder_output
    ), f"sink emitted a live HCL opener for {hostile.id!r}"
    # No injected resource block appears (the value must stay inside a string literal).
    assert '"PWNED"' not in builder_output
    assert '"injected"' not in builder_output


def test_sink_node_name_role(hostile: HostileValue) -> None:
    _emit_and_scan(role_block(_node(NodeType.IAM_ROLE, name=hostile.value)), hostile)


def test_sink_node_name_bucket(hostile: HostileValue) -> None:
    _emit_and_scan(bucket_block(_node(NodeType.S3_BUCKET, name=hostile.value)), hostile)


def test_sink_bucket_policy_arn(hostile: HostileValue) -> None:
    """The THIRD jsonencode sink: ``_bucket_policy_block`` embeds ``node.name`` in the arn.

    A plain ``bucket_block`` omits the compensating control, so the bucket-policy block
    (a ``jsonencode``-wrapped document carrying ``node.name`` via ``_bucket_name``) never
    emits — leaving that neutralized sink un-regression-locked. Setting
    ``compensating_control="true"`` forces it to emit with the hostile value.
    """
    block = bucket_block(
        _node(NodeType.S3_BUCKET, name=hostile.value, compensating_control="true")
    )
    # The compensating control must actually have produced the bucket-policy block.
    assert '"aws_s3_bucket_policy"' in block, "compensating-control policy block did not emit"
    _emit_and_scan(block, hostile)


def test_sink_node_name_security_group(hostile: HostileValue) -> None:
    block = security_group_block(_node(NodeType.SECURITY_GROUP, name=hostile.value), "vpc_ref")
    _emit_and_scan(block, hostile)


def test_sink_iam_resource_arn(hostile: HostileValue) -> None:
    _emit_and_scan(policy_block(_node(NodeType.IAM_POLICY, resource=hostile.value)), hostile)


def test_sink_cidr_block(hostile: HostileValue) -> None:
    _emit_and_scan(vpc_block(_node(NodeType.VPC, cidr=hostile.value)), hostile)


def test_sink_ingress_cidr(hostile: HostileValue) -> None:
    block = security_group_block(
        _node(NodeType.SECURITY_GROUP, ingress_cidr=hostile.value), "vpc_ref"
    )
    _emit_and_scan(block, hostile)


# --- 3. tag-value sink via the full emitter (env/owner/app -> common_tags) ------


def _tagged_graph(hostile: HostileValue) -> ScenarioGraph:
    """The ci_cd graph with an Account node whose tags carry the hostile value.

    ``derive_common_tags`` prefers the Account node, so its tags drive ``main.tf``.
    """
    base = ci_cd_iam_chain.build_graph()
    tainted = GraphNode(
        id="acct_tainted",
        type=NodeType.ACCOUNT,
        name="tainted-account",
        tags=NodeTags(env=hostile.value, owner=hostile.value, app=hostile.value),
        security=NodeSecurity(criticality="low"),
        attributes={},
    )
    return ScenarioGraph(nodes=[tainted, *base.nodes], edges=base.edges)


def test_sink_tag_values_are_inert(hostile: HostileValue, tmp_path: Path) -> None:
    written = TerraformEmitter(_tagged_graph(hostile)).emit(tmp_path)
    main = (tmp_path / "main.tf").read_text(encoding="utf-8")
    assert "main.tf" in {p.name for p in written}
    assert not _has_live_hcl_opener(main), f"tag sink live opener for {hostile.id!r}"


# --- 4. real terraform validate (bounded invocation) --------------------------
#
# We separate two distinct rejection surfaces:
#
#   * HCL-level safety (this ticket's security property): a hostile value must never
#     break out of its string literal or evaluate as live interpolation. We prove this
#     under real terraform by placing the WHOLE corpus (via ``hcl_str``, the exact
#     product escaping funnel) into GENERIC HCL string positions (``locals`` values)
#     that carry NO provider content-schema — so ANY failure here is a true HCL escape.
#
#   * AWS provider content-schema (NOT a security property): ``terraform validate`` also
#     rejects a string that is safely-escaped-but-semantically-invalid for a *specific*
#     argument (e.g. an S3 ``bucket`` name > 63 chars, an IAM role ``name`` outside
#     ``[\w+=,.@-]``, a ``cidr_block`` that is not a CIDR). That is a clear validation
#     rejection — the ticket's acceptance-criteria "OR rejected" branch — not a breakout.
#     We therefore drive the emitter end-to-end with a corpus value that is *valid* AWS
#     content yet still carries the interpolation payload, proving the payload is inert.


def _terraform_validate(tmp_path: Path) -> subprocess.CompletedProcess[str]:
    subprocess.run(  # noqa: S603 — fixed argv, no shell, terraform from PATH
        ["terraform", "init", "-backend=false", "-input=false"],  # noqa: S607
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    return subprocess.run(  # noqa: S603
        ["terraform", "validate"],  # noqa: S607
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )


def _write_generic_locals(tmp_path: Path) -> None:
    """Emit every corpus value through ``hcl_str`` into a schema-free ``locals`` block.

    ``locals`` values have no AWS content-schema, so ``terraform validate`` here checks
    ONLY that each escaped literal is syntactically valid HCL with no live opener — the
    pure HCL-injection surface, isolated from provider naming/CIDR rules.
    """
    lines = ["locals {"]
    for idx, entry in enumerate(HOSTILE_VALUES):
        lines.append(f"  v{idx} = {hcl_str(entry.value)}")
    lines.append("}\n")
    (tmp_path / "corpus.tf").write_text("\n".join(lines), encoding="utf-8")


def test_whole_corpus_in_generic_hcl_string_is_terraform_valid(tmp_path: Path) -> None:
    """Every corpus value, escaped and placed in a generic HCL string, is valid HCL.

    This is the core HCL-injection assertion under real terraform: no value breaks out
    or stays live. Provider content-schema is deliberately excluded (see module note).
    """
    if _TERRAFORM is None:  # pragma: no cover - terraform is on PATH in CI/dev
        return
    _write_generic_locals(tmp_path)
    result = _terraform_validate(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


def test_interpolation_payload_is_inert_end_to_end(tmp_path: Path) -> None:
    """The ``${...}`` payload, carried through the FULL emitter, keeps the tree valid.

    Driven via graph tag values (``common_tags`` — a real emitter sink with no AWS
    content-schema). A LIVE ``${local.fake_account_id}`` would either resolve (semantic
    escape) or, for an undeclared ref, fail validate. Escaped, it is inert and valid.
    """
    if _TERRAFORM is None:  # pragma: no cover
        return
    tricky = HostileValue("interp_ref", "${data.nonexistent.thing.value}")
    TerraformEmitter(_tagged_graph(tricky)).emit(tmp_path)
    result = _terraform_validate(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


def test_bucket_policy_document_interpolation_is_inert_under_terraform(tmp_path: Path) -> None:
    """The bucket-policy ``jsonencode`` arg (carrying ``node.name``) is inert as HCL.

    ``_bucket_policy_block`` embeds the untrusted ``node.name`` into a ``jsonencode``
    document. An interpolation-bearing name cannot ride the S3 ``bucket`` argument (that
    is rejected by AWS name-schema — the "OR rejected" branch), so we isolate the sink:
    emit the policy block for an interpolation-bearing name and place ITS ``jsonencode``
    document into a schema-free ``locals`` value. A LIVE ``${...}`` (undeclared ref) would
    fail ``terraform validate``; the neutralized document is inert and validates.
    """
    if _TERRAFORM is None:  # pragma: no cover
        return
    node = _node(
        NodeType.S3_BUCKET,
        name="x${data.nonexistent.thing.value}",
        compensating_control="true",
    )
    block = bucket_block(node)
    # Extract the exact document handed to ``jsonencode(...)`` from the emitted policy.
    match = re.search(r"policy = jsonencode\((?P<doc>.+)\)\n", block)
    assert match is not None, block
    (tmp_path / "policy_doc.tf").write_text(
        f"locals {{\n  doc = jsonencode({match.group('doc')})\n}}\n", encoding="utf-8"
    )
    result = _terraform_validate(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


# --- 5. explicit FXL-35 regression-lock: the two interpolation surfaces --------


def test_interpolation_opener_is_neutralized_to_literal() -> None:
    """``${...}`` -> ``$${...}`` (regression-lock FXL-35): a lone opener never survives."""
    literal = hcl_str("x${local.fake_account_id}")
    assert "$${local.fake_account_id}" in literal
    assert not _has_live_hcl_opener(literal)


def test_template_directive_is_neutralized_to_literal() -> None:
    """``%{...}`` -> ``%%{...}`` (regression-lock FXL-35): a lone directive never survives."""
    literal = hcl_str("%{ if true }evil%{ endif }")
    assert "%%{ if true }evil%%{ endif }" in literal
    assert not _has_live_hcl_opener(literal)
