"""Hardcoded ``public_data_exposure`` scenario data.

Story: a prod b2b_saas data lake where a public-read S3 bucket (``customer-pii``)
is reachable from the internet and holds a sensitive customer-PII dataset, with no
compensating control. That direct exposure is the critical risk — distinct from the
IAM privilege *chain* of ``ci_cd_iam_chain``: no role-assumption hop, the data is
one bucket-policy away from the public. Supporting findings: the public-read
exposure, a missing-logging gap, and one benign false-positive (a public-looking
backups bucket that a bucket policy actually locks down).

All ids/names/edges here are the single source the graph, ground truth, expected
findings, and Terraform emitter agree on.
"""

from __future__ import annotations

from app.cloudforge.models.findings import (
    ExpectedFinding,
    ExpectedFindings,
    FindingFamily,
    GroundTruthPath,
    GroundTruthPaths,
)
from app.cloudforge.models.graph import (
    Criticality,
    EdgeRisk,
    EdgeSecurity,
    EdgeType,
    GraphEdge,
    GraphNode,
    NodeSecurity,
    NodeTags,
    NodeType,
    ScenarioGraph,
)

_TAGS = NodeTags(env="prod", owner="data-platform-team", app="customer-data-lake")
_CRITICAL_PATH_ID = "path-critical-pde-01"


def _node(
    node_id: str,
    node_type: NodeType,
    name: str,
    crit: Criticality,
    **attrs: str | list[str],
) -> GraphNode:
    return GraphNode(
        id=node_id,
        type=node_type,
        name=name,
        tags=_TAGS,
        security=NodeSecurity(criticality=crit),
        attributes=dict(attrs),
    )


def _edge(src: str, dst: str, edge_type: EdgeType, risk: EdgeRisk) -> GraphEdge:
    return GraphEdge(from_=src, to=dst, type=edge_type, security=EdgeSecurity(risk=risk))


def _build_nodes() -> list[GraphNode]:
    return [
        _node("acct-main", NodeType.ACCOUNT, "prod-account", "high"),
        _node("vpc-prod", NodeType.VPC, "prod-vpc", "low", cidr="10.1.0.0/16"),
        _node(
            "s3-public-data",
            NodeType.S3_BUCKET,
            "customer-pii",
            "critical",
            public_access="enabled",
            acl="public-read",
            logging="disabled",
        ),
        _node(
            "s3-locked-backups",
            NodeType.S3_BUCKET,
            "public-looking-backups",
            "medium",
            public_access="enabled",
            compensating_control="true",
        ),
        _node("app-data-lake", NodeType.APPLICATION, "customer-data-lake", "high"),
        _node("data-customer-pii", NodeType.DATASET, "customer-pii-records", "critical"),
        _node("trail-main", NodeType.LOG_TRAIL, "main-trail", "medium"),
    ]


def _build_edges() -> list[GraphEdge]:
    return [
        _edge("acct-main", "s3-public-data", EdgeType.EXPOSED_TO_INTERNET, "critical"),
        _edge(
            "s3-public-data",
            "data-customer-pii",
            EdgeType.STORES_SENSITIVE_DATA,
            "critical",
        ),
        _edge("s3-public-data", "app-data-lake", EdgeType.BELONGS_TO_APP, "low"),
        _edge("s3-locked-backups", "app-data-lake", EdgeType.BELONGS_TO_APP, "low"),
        _edge("acct-main", "s3-locked-backups", EdgeType.EXPOSED_TO_INTERNET, "low"),
        # NOTE: no `s3-public-data -> logs_to -> trail-main` edge — the *absence*
        # is the s3_logging_missing finding.
    ]


def build_graph() -> ScenarioGraph:
    return ScenarioGraph(nodes=_build_nodes(), edges=_build_edges())


def build_ground_truth() -> GroundTruthPaths:
    critical = GroundTruthPath(
        id=_CRITICAL_PATH_ID,
        severity="critical",
        nodes=["acct-main", "s3-public-data", "data-customer-pii"],
        edges=[
            "acct-main->exposed_to_internet->s3-public-data",
            "s3-public-data->stores_sensitive_data->data-customer-pii",
        ],
        explanation=(
            "The customer-pii bucket has public-read access with no compensating "
            "control, so it is reachable directly from the internet -> anonymous read "
            "of the sensitive customer-PII dataset it stores."
        ),
    )
    return GroundTruthPaths(paths=[critical])


def build_findings() -> ExpectedFindings:
    return ExpectedFindings(findings=[_public_exposure(), _logging(), _false_positive()])


def _public_exposure() -> ExpectedFinding:
    return ExpectedFinding(
        id="find-pde-public-01",
        severity="critical",
        family=FindingFamily.S3_PUBLIC_EXPOSURE,
        resource_ids=["s3-public-data", "data-customer-pii"],
        expected_scanner_visibility="visible",
        ground_truth="customer-pii allows public read and stores sensitive data.",
        remediation=(
            "Enable S3 Block Public Access and remove the public-read ACL/bucket policy."
        ),
    )


def _logging() -> ExpectedFinding:
    return ExpectedFinding(
        id="find-pde-logging-01",
        severity="medium",
        family=FindingFamily.S3_LOGGING_MISSING,
        resource_ids=["s3-public-data", "trail-main"],
        expected_scanner_visibility="visible",
        ground_truth="The public bucket has no access logging / CloudTrail data events.",
        remediation="Enable S3 access logging and CloudTrail data events for the bucket.",
    )


def _false_positive() -> ExpectedFinding:
    return ExpectedFinding(
        id="find-pde-fp-01",
        severity="low",
        family=FindingFamily.PUBLIC_LOOKING_BUCKET_WITH_COMPENSATING_CONTROL,
        resource_ids=["s3-locked-backups"],
        expected_scanner_visibility="visible",
        ground_truth="benign",
        remediation=(
            "None needed — a bucket policy restricts access despite the public-looking name."
        ),
    )
