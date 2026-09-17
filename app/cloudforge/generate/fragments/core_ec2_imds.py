"""``core.ec2_imds_credential_exfil``: EC2 IMDSv1 SSRF and IAM credential exfil.

Story: a public web instance still serves IMDSv1, so a server-side request
steals the credentials of WebAppInstanceRole. That role reads the customer PII
bucket directly on the direct chain; with ``extra_hops`` it chains by
``sts:AssumeRole`` through intermediate roles and the last one holds the read
grant. With ``dead_end`` the instance can also invoke a function that runs as a
role reading nothing.
"""

from __future__ import annotations

from random import Random
from typing import Any

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

_TAGS = NodeTags(env="prod", owner="web-platform-team", app="customer-portal")
_ENTRY = "ec2-web-frontend"
_HEAD = "role-web-app"
_BUCKET = "s3-customer-pii"
_SINK = "data-customer-pii"


@register("core.ec2_imds_credential_exfil")
class Ec2ImdsCredentialExfil:
    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        kit = Kit(ns, _TAGS)
        shape = shape_of(params)
        hops = draw_hops(kit, rng, shape.extra_hops, AWS_HOP_ROLES, "role", NodeType.IAM_ROLE)
        chain = [_HEAD, *hops.ids]
        nodes = _nodes(kit) + hops.nodes
        edges = _edges(kit, chain)
        if shape.dead_end:
            branch = aws.dead_end_function(kit, rng, _ENTRY)
            nodes, edges = nodes + branch.nodes, edges + branch.edges
        names = ["WebAppInstanceRole", *hops.names]
        return FragmentBundle(
            nodes=nodes,
            edges=edges,
            findings=_findings(kit, chain[-1]),
            paths=[_critical(kit, chain, names)],
        )


def _nodes(kit: Kit) -> list[GraphNode]:
    return [
        kit.node("acct-main", NodeType.ACCOUNT, "prod-account", "medium"),
        kit.node(_ENTRY, NodeType.EC2_INSTANCE, "WebFrontendServer", "high", imds_version="v1"),
        kit.node(_HEAD, NodeType.IAM_ROLE, "WebAppInstanceRole", "high"),
        kit.node(
            "pol-app-data",
            NodeType.IAM_POLICY,
            "WebAppCustomerDataPolicy",
            "high",
            actions=["s3:Get*", "s3:List*"],
        ),
        kit.node(_BUCKET, NodeType.S3_BUCKET, "customer-pii-records-000000000000", "critical"),
        kit.node(
            _SINK,
            NodeType.DATASET,
            "customer-identity-and-pii",
            "critical",
            classification="restricted",
        ),
    ]


def _edges(kit: Kit, chain: list[str]) -> list[GraphEdge]:
    reader = chain[-1]
    return [
        kit.edge("acct-main", _ENTRY, EdgeType.EXPOSED_TO_INTERNET, "critical"),
        kit.edge(_ENTRY, _HEAD, EdgeType.ASSUMES, "critical"),
        *kit.chain(chain, EdgeType.ASSUMES, "critical"),
        kit.edge(reader, "pol-app-data", EdgeType.ATTACHED_POLICY, "high"),
        kit.edge(reader, _BUCKET, EdgeType.CAN_READ, "critical"),
        kit.edge(_BUCKET, _SINK, EdgeType.STORES_SENSITIVE_DATA, "none"),
    ]


def _findings(kit: Kit, reader: str) -> list[ExpectedFinding]:
    return [
        ExpectedFinding(
            id=kit.nid("finding-ec2-imdsv1-enabled-01"),
            severity="critical",
            family=FindingFamily.EC2_IMDSV1_ENABLED,
            resource_ids=[kit.nid(_ENTRY)],
            expected_scanner_visibility="visible",
            ground_truth="Public EC2 instance permits IMDSv1 exposing temporary STS credentials",
            remediation="Enforce IMDSv2 by setting http_tokens = 'required' on the instance",
        ),
        ExpectedFinding(
            id=kit.nid("finding-iam-excessive-privilege-01"),
            severity="high",
            family=FindingFamily.IAM_EXCESSIVE_PRIVILEGE,
            resource_ids=[kit.nid(reader), kit.nid("pol-app-data")],
            expected_scanner_visibility="visible",
            ground_truth="The role that reads customer PII holds broad s3:Get* permissions",
            remediation="Scope IAM policy to explicit GetObject actions on required prefixes",
        ),
    ]


def _critical(kit: Kit, chain: list[str], names: list[str]) -> GroundTruthPath:
    reader = chain[-1]
    return GroundTruthPath(
        id=kit.nid("path-critical-imds-01"),
        severity="critical",
        nodes=[kit.nid(n) for n in [_ENTRY, *chain, _BUCKET, _SINK]],
        edges=[
            kit.ek(_ENTRY, EdgeType.ASSUMES, _HEAD),
            *kit.chain_keys(chain, EdgeType.ASSUMES),
            kit.ek(reader, EdgeType.CAN_READ, _BUCKET),
            kit.ek(_BUCKET, EdgeType.STORES_SENSITIVE_DATA, _SINK),
        ],
        sink_kind=SinkKind.DATA,
        target=kit.nid(_SINK),
        explanation=(
            "Public web instance with IMDSv1 enables SSRF theft of WebAppInstanceRole "
            "credentials"
            + (f"; {hop_lines(names, 'assumes')}" if len(names) > 1 else "")
            + f"; {names[-1]} reads customer-pii-records"
        ),
    )
