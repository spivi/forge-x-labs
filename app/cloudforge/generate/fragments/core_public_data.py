"""``core.public_data_exposure`` fragment — direct public S3 exposure.

Story: a public-read S3 bucket (``customer-pii``) is reachable from the
internet and holds a sensitive customer-PII dataset, with no compensating
control. That direct exposure is the critical risk — distinct from the IAM
privilege *chain* of ``core.ci_cd_iam_chain``: no role-assumption hop, the
data is one bucket-policy away from the public. Supporting findings: the
public-read exposure, a missing-logging gap, and one benign false-positive
(a public-looking backups bucket that a bucket policy actually locks down).

Ported from the legacy ``generate/public_data_exposure.py`` hardcoded
generator; every id is namespaced by ``ns`` so composed bundles stay
self-consistent.
"""

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

_TAGS = NodeTags(env="prod", owner="data-platform-team", app="customer-data-lake")


def _node(
    ns: str, node_id: str, node_type: NodeType, name: str, crit: str, **attrs: str | list[str]
) -> GraphNode:
    return GraphNode(
        id=f"{ns}/{node_id}",
        type=node_type,
        name=name,
        tags=_TAGS,
        security=NodeSecurity(criticality=crit),
        attributes=dict(attrs),
    )


def _edge(ns: str, src: str, dst: str, edge_type: EdgeType, risk: str) -> GraphEdge:
    return GraphEdge(
        from_=f"{ns}/{src}", to=f"{ns}/{dst}", type=edge_type, security=EdgeSecurity(risk=risk)
    )


@register("core.public_data_exposure")
class PublicDataExposure:
    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        return FragmentBundle(
            nodes=_nodes(ns),
            edges=_edges(ns),
            findings=_findings(ns),
            paths=[_critical(ns)],
        )


def _nodes(ns: str) -> list[GraphNode]:
    return [
        _node(ns, "acct-main", NodeType.ACCOUNT, "prod-account", "high"),
        _node(ns, "vpc-prod", NodeType.VPC, "prod-vpc", "low", cidr="10.1.0.0/16"),
        _node(
            ns,
            "s3-public-data",
            NodeType.S3_BUCKET,
            "customer-pii",
            "critical",
            public_access="enabled",
            acl="public-read",
            logging="disabled",
        ),
        _node(
            ns,
            "s3-locked-backups",
            NodeType.S3_BUCKET,
            "public-looking-backups",
            "medium",
            public_access="enabled",
            compensating_control="true",
        ),
        _node(ns, "app-data-lake", NodeType.APPLICATION, "customer-data-lake", "high"),
        _node(
            ns,
            "data-customer-pii",
            NodeType.DATASET,
            "customer-pii-records",
            "critical",
            classification="restricted",
        ),
        _node(ns, "trail-main", NodeType.LOG_TRAIL, "main-trail", "medium"),
    ]


def _edges(ns: str) -> list[GraphEdge]:
    return [
        _edge(ns, "acct-main", "s3-public-data", EdgeType.EXPOSED_TO_INTERNET, "critical"),
        _edge(
            ns, "s3-public-data", "data-customer-pii", EdgeType.STORES_SENSITIVE_DATA, "critical"
        ),
        _edge(ns, "s3-public-data", "app-data-lake", EdgeType.BELONGS_TO_APP, "low"),
        _edge(ns, "s3-locked-backups", "app-data-lake", EdgeType.BELONGS_TO_APP, "low"),
        _edge(ns, "acct-main", "s3-locked-backups", EdgeType.EXPOSED_TO_INTERNET, "low"),
        # NOTE: no `s3-public-data -> logs_to -> trail-main` edge — the
        # *absence* is the s3_logging_missing finding.
    ]


def _critical(ns: str) -> GroundTruthPath:
    return GroundTruthPath(
        id=f"{ns}/path-critical-pde-01",
        severity="critical",
        nodes=[f"{ns}/acct-main", f"{ns}/s3-public-data", f"{ns}/data-customer-pii"],
        edges=[
            f"{ns}/acct-main->{EdgeType.EXPOSED_TO_INTERNET.value}->{ns}/s3-public-data",
            f"{ns}/s3-public-data->{EdgeType.STORES_SENSITIVE_DATA.value}->{ns}/data-customer-pii",
        ],
        explanation=(
            "The customer-pii bucket has public-read access with no compensating "
            "control, so it is reachable directly from the internet -> anonymous "
            "read of the sensitive customer-PII dataset it stores."
        ),
    )


def _findings(ns: str) -> list[ExpectedFinding]:
    return [_public_exposure_finding(ns), _logging_finding(ns), _false_positive_finding(ns)]


def _public_exposure_finding(ns: str) -> ExpectedFinding:
    return ExpectedFinding(
        id=f"{ns}/find-pde-public-01",
        severity="critical",
        family=FindingFamily.S3_PUBLIC_EXPOSURE,
        resource_ids=[f"{ns}/s3-public-data", f"{ns}/data-customer-pii"],
        expected_scanner_visibility="visible",
        ground_truth="customer-pii allows public read and stores sensitive data.",
        remediation=(
            "Enable S3 Block Public Access and remove the public-read ACL/bucket policy."
        ),
    )


def _logging_finding(ns: str) -> ExpectedFinding:
    return ExpectedFinding(
        id=f"{ns}/find-pde-logging-01",
        severity="medium",
        family=FindingFamily.S3_LOGGING_MISSING,
        resource_ids=[f"{ns}/s3-public-data", f"{ns}/trail-main"],
        expected_scanner_visibility="visible",
        ground_truth="The public bucket has no access logging / CloudTrail data events.",
        remediation="Enable S3 access logging and CloudTrail data events for the bucket.",
    )


def _false_positive_finding(ns: str) -> ExpectedFinding:
    return ExpectedFinding(
        id=f"{ns}/find-pde-fp-01",
        severity="low",
        family=FindingFamily.PUBLIC_LOOKING_BUCKET_WITH_COMPENSATING_CONTROL,
        resource_ids=[f"{ns}/s3-locked-backups"],
        expected_scanner_visibility="visible",
        ground_truth="benign",
        remediation=(
            "None needed — a bucket policy restricts access despite the public-looking name."
        ),
    )
