"""``core.cross_account_trust`` fragment: an external account trusted into a role.

Story: a dummy partner account (``999999999999``) is trusted by a role inside
this account. What the attacker reaches is SharedRole (``sink_kind`` ``role``),
the role holding ``s3:Get*/List*`` on the partner-exchange bucket: on the direct
chain the partner account assumes SharedRole itself; with ``extra_hops`` the
trust lands on another role that chains into SharedRole by ``sts:AssumeRole``,
one hop per drawn role. The data SharedRole can read is the second,
high-severity path. With ``dead_end`` the partner account can also assume a
second role whose grant reaches nothing.
"""

from __future__ import annotations

from random import Random
from typing import Any

from app.cloudforge import constants
from app.cloudforge.generate.fragments import _aws_shape as aws
from app.cloudforge.generate.fragments._core import Kit, draw_hops, hop_lines, shape_of
from app.cloudforge.generate.fragments._vocab import AWS_HOP_ROLES
from app.cloudforge.generate.fragments.base import FragmentBundle, register
from app.cloudforge.models.findings import (
    ExpectedFinding,
    FindingFamily,
    GroundTruthPath,
    SinkKind,
)
from app.cloudforge.models.graph import EdgeType, GraphEdge, GraphNode, NodeTags, NodeType

_TAGS = NodeTags(env="prod", owner="partner-integrations", app="partner-exchange")
_EXT = constants.EXTERNAL_DUMMY_ACCOUNT_ID
_TRUST = f"arn:aws:iam::{_EXT}:root"
_BUCKET_ARN = "arn:aws:s3:::partner-exchange"
_ENTRY = "acct-external"
_SINK = "role-shared"


@register("core.cross_account_trust")
class CrossAccountTrust:
    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        kit = Kit(ns, _TAGS)
        shape = shape_of(params)
        hops = draw_hops(kit, rng, shape.extra_hops, AWS_HOP_ROLES, "role", NodeType.IAM_ROLE)
        chain = [*hops.ids, _SINK]
        nodes = _nodes(kit, trusted=chain[0] == _SINK) + hops.nodes
        if hops.nodes:
            hops.nodes[0].attributes["trusted_principal"] = _TRUST
        edges = _edges(kit, chain)
        if shape.dead_end:
            branch = aws.dead_end_role(kit, rng, _ENTRY)
            nodes, edges = nodes + branch.nodes, edges + branch.edges
        names = [*hops.names, "SharedRole"]
        return FragmentBundle(
            nodes=nodes,
            edges=edges,
            findings=_findings(kit, chain[0]),
            paths=[_critical(kit, chain, names), _data_path(kit)],
        )


def _nodes(kit: Kit, *, trusted: bool) -> list[GraphNode]:
    trust: dict[str, str] = {"trusted_principal": _TRUST} if trusted else {}
    return [
        kit.node(_ENTRY, NodeType.ACCOUNT, "partner-account", "high", account_id=_EXT),
        kit.node("acct-main", NodeType.ACCOUNT, "prod-account", "medium"),
        kit.node(_SINK, NodeType.IAM_ROLE, "SharedRole", "critical", **trust),
        kit.node(
            "pol-shared-s3read",
            NodeType.IAM_POLICY,
            "SharedS3ReadPolicy",
            "high",
            actions=["s3:Get*", "s3:List*"],
            resource=f"{_BUCKET_ARN}/*",
        ),
        kit.node(
            "s3-partner-data",
            NodeType.S3_BUCKET,
            "partner-exchange",
            "critical",
            logging="disabled",
        ),
        kit.node(
            "s3-locked-backups",
            NodeType.S3_BUCKET,
            "public-looking-backups",
            "medium",
            public_access="enabled",
            compensating_control="true",
        ),
        kit.node("app-partner-exchange", NodeType.APPLICATION, "partner-exchange", "medium"),
        kit.node(
            "data-partner",
            NodeType.DATASET,
            "partner-records",
            "critical",
            classification="restricted",
        ),
        kit.node("trail-main", NodeType.LOG_TRAIL, "main-trail", "medium"),
    ]


def _edges(kit: Kit, chain: list[str]) -> list[GraphEdge]:
    return [
        kit.edge(_ENTRY, chain[0], EdgeType.ASSUMES, "critical"),
        *kit.chain(chain, EdgeType.ASSUMES, "critical"),
        kit.edge(_SINK, "pol-shared-s3read", EdgeType.ATTACHED_POLICY, "high"),
        kit.edge(_SINK, "s3-partner-data", EdgeType.CAN_READ, "critical"),
        kit.edge("s3-partner-data", "data-partner", EdgeType.STORES_SENSITIVE_DATA, "critical"),
        kit.edge("s3-partner-data", "app-partner-exchange", EdgeType.BELONGS_TO_APP, "low"),
        kit.edge("s3-locked-backups", "app-partner-exchange", EdgeType.BELONGS_TO_APP, "low"),
    ]


def _critical(kit: Kit, chain: list[str], names: list[str]) -> GroundTruthPath:
    return GroundTruthPath(
        id=kit.nid("path-critical-xacct-01"),
        severity="critical",
        nodes=[kit.nid(n) for n in [_ENTRY, *chain]],
        edges=[
            kit.ek(_ENTRY, EdgeType.ASSUMES, chain[0]),
            *kit.chain_keys(chain, EdgeType.ASSUMES),
        ],
        sink_kind=SinkKind.ROLE,
        target=kit.nid(_SINK),
        explanation=(
            f"Partner account {_EXT} is trusted to assume {names[0]}"
            + (f"; {hop_lines(names, 'assumes')}" if len(names) > 1 else "")
            + ", so an external principal holds SharedRole inside this account."
        ),
    )


def _data_path(kit: Kit) -> GroundTruthPath:
    return GroundTruthPath(
        id=kit.nid("path-high-xacct-data-01"),
        severity="high",
        nodes=[kit.nid(_SINK), kit.nid("s3-partner-data"), kit.nid("data-partner")],
        edges=[
            kit.ek(_SINK, EdgeType.CAN_READ, "s3-partner-data"),
            kit.ek("s3-partner-data", EdgeType.STORES_SENSITIVE_DATA, "data-partner"),
        ],
        sink_kind=SinkKind.DATA,
        target=kit.nid("data-partner"),
        explanation=(
            "SharedRole holds s3:Get*/List* on partner-exchange, which stores sensitive "
            "partner records: what the trusted role can read once it is held."
        ),
    )


def _findings(kit: Kit, trusted: str) -> list[ExpectedFinding]:
    return [_trust_finding(kit, trusted), _logging_finding(kit), _false_positive_finding(kit)]


def _trust_finding(kit: Kit, trusted: str) -> ExpectedFinding:
    resources = [kit.nid(_ENTRY), kit.nid(trusted), kit.nid(_SINK)]
    return ExpectedFinding(
        id=kit.nid("find-xacct-01"),
        severity="critical",
        family=FindingFamily.IAM_CROSS_ACCOUNT_TRUST,
        resource_ids=[
            *dict.fromkeys(resources),
            kit.nid("pol-shared-s3read"),
            kit.nid("s3-partner-data"),
        ],
        expected_scanner_visibility="partial",
        ground_truth="An external dummy account is trusted into a role that can read data.",
        remediation="Restrict the trust policy to a named partner role, not account root.",
    )


def _logging_finding(kit: Kit) -> ExpectedFinding:
    return ExpectedFinding(
        id=kit.nid("find-xacct-logging-01"),
        severity="medium",
        family=FindingFamily.S3_LOGGING_MISSING,
        resource_ids=[kit.nid("s3-partner-data"), kit.nid("trail-main")],
        expected_scanner_visibility="visible",
        ground_truth="The partner-exchange bucket has no access logging.",
        remediation="Enable S3 access logging and CloudTrail data events for the bucket.",
    )


def _false_positive_finding(kit: Kit) -> ExpectedFinding:
    return ExpectedFinding(
        id=kit.nid("find-xacct-fp-01"),
        severity="low",
        family=FindingFamily.PUBLIC_LOOKING_BUCKET_WITH_COMPENSATING_CONTROL,
        resource_ids=[kit.nid("s3-locked-backups")],
        expected_scanner_visibility="visible",
        ground_truth="benign",
        remediation="None needed: a bucket policy restricts access despite the name.",
    )
