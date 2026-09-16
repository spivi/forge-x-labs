"""``core.ec2_imds_credential_exfil`` — EC2 IMDSv1 SSRF and IAM credential exfil."""

from __future__ import annotations

from random import Random
from typing import Any

from app.cloudforge.generate.fragments.base import FragmentBundle, register
from app.cloudforge.models.findings import ExpectedFinding, FindingFamily, GroundTruthPath
from app.cloudforge.models.graph import (
    EdgeSecurity,
    EdgeType,
    GraphEdge,
    GraphNode,
    NodeSecurity,
    NodeTags,
    NodeType,
)

_TAGS = NodeTags(env="prod", owner="web-platform-team", app="customer-portal")


def _nid(ns: str, node_id: str) -> str:
    return f"{ns}/{node_id}" if ns else node_id


def _node(
    ns: str, node_id: str, node_type: NodeType, name: str, crit: str, **attrs: str | list[str]
) -> GraphNode:
    return GraphNode(
        id=_nid(ns, node_id),
        type=node_type,
        name=name,
        tags=_TAGS,
        security=NodeSecurity(criticality=crit),
        attributes=dict(attrs),
    )


def _edge(ns: str, src: str, dst: str, edge_type: EdgeType, risk: str) -> GraphEdge:
    return GraphEdge(
        from_=_nid(ns, src),
        to=_nid(ns, dst),
        type=edge_type,
        security=EdgeSecurity(risk=risk),
    )


@register("core.ec2_imds_credential_exfil")
class Ec2ImdsCredentialExfil:
    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        return FragmentBundle(
            nodes=_nodes(ns),
            edges=_edges(ns),
            findings=_findings(ns),
            paths=[_critical(ns)],
        )


def _nodes(ns: str) -> list[GraphNode]:
    return [
        _node(ns, "acct-main", NodeType.ACCOUNT, "prod-account", "medium"),
        _node(
            ns,
            "ec2-web-frontend",
            NodeType.EC2_INSTANCE,
            "WebFrontendServer",
            "high",
            imds_version="v1",
        ),
        _node(ns, "role-web-app", NodeType.IAM_ROLE, "WebAppInstanceRole", "high"),
        _node(
            ns,
            "pol-app-data",
            NodeType.IAM_POLICY,
            "WebAppCustomerDataPolicy",
            "high",
            actions=["s3:Get*", "s3:List*"],
        ),
        _node(
            ns,
            "s3-customer-pii",
            NodeType.S3_BUCKET,
            "customer-pii-records-000000000000",
            "critical",
        ),
        _node(
            ns,
            "data-customer-pii",
            NodeType.DATASET,
            "CustomerIdentityAndPII",
            "critical",
        ),
    ]


def _edges(ns: str) -> list[GraphEdge]:
    return [
        _edge(ns, "acct-main", "ec2-web-frontend", EdgeType.EXPOSED_TO_INTERNET, "critical"),
        _edge(ns, "ec2-web-frontend", "role-web-app", EdgeType.ASSUMES, "critical"),
        _edge(ns, "role-web-app", "pol-app-data", EdgeType.ATTACHED_POLICY, "high"),
        _edge(ns, "role-web-app", "s3-customer-pii", EdgeType.CAN_READ, "critical"),
        _edge(
            ns,
            "s3-customer-pii",
            "data-customer-pii",
            EdgeType.STORES_SENSITIVE_DATA,
            "none",
        ),
    ]


def _findings(ns: str) -> list[ExpectedFinding]:
    return [
        ExpectedFinding(
            id=_nid(ns, "finding-ec2-imdsv1-enabled-01"),
            severity="critical",
            family=FindingFamily.EC2_IMDSV1_ENABLED,
            resource_ids=[_nid(ns, "ec2-web-frontend")],
            expected_scanner_visibility="visible",
            ground_truth="Public EC2 instance permits IMDSv1 exposing temporary STS credentials",
            remediation="Enforce IMDSv2 by setting http_tokens = 'required' on the instance",
        ),
        ExpectedFinding(
            id=_nid(ns, "finding-iam-excessive-privilege-01"),
            severity="high",
            family=FindingFamily.IAM_EXCESSIVE_PRIVILEGE,
            resource_ids=[_nid(ns, "role-web-app"), _nid(ns, "pol-app-data")],
            expected_scanner_visibility="visible",
            ground_truth="Web app role holds broad s3:Get* permissions on customer PII",
            remediation="Scope IAM policy to explicit GetObject actions on required prefixes",
        ),
    ]


def _ek(ns: str, src: str, edge_type: EdgeType, dst: str) -> str:
    return f"{_nid(ns, src)}->{edge_type.value}->{_nid(ns, dst)}"


def _critical(ns: str) -> GroundTruthPath:
    return GroundTruthPath(
        id=_nid(ns, "path-critical-imds-01"),
        severity="critical",
        nodes=[
            _nid(ns, "ec2-web-frontend"),
            _nid(ns, "role-web-app"),
            _nid(ns, "s3-customer-pii"),
            _nid(ns, "data-customer-pii"),
        ],
        edges=[
            _ek(ns, "ec2-web-frontend", EdgeType.ASSUMES, "role-web-app"),
            _ek(ns, "role-web-app", EdgeType.CAN_READ, "s3-customer-pii"),
            _ek(ns, "s3-customer-pii", EdgeType.STORES_SENSITIVE_DATA, "data-customer-pii"),
        ],
        explanation=(
            "Public web instance with IMDSv1 enables SSRF "
            "credential theft to access PII records"
        ),
    )
