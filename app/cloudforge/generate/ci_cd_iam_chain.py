"""Hardcoded ``ci_cd_iam_chain`` scenario data.

Story: a staging b2b_saas env where a GitHub Actions OIDC identity assumes a
DeployRole, which can ``iam:PassRole`` a RuntimeRole that holds broad S3 read over
a sensitive customer-exports bucket. That chain is the critical risk. Supporting
findings: an overly-broad S3 read, a missing-logging gap, an over-exposed security
group, and one benign false-positive (a public-looking bucket with a compensating
control).

All ids/names/edges here are the single source the graph, ground truth, expected
findings, and Terraform emitter agree on.
"""

from __future__ import annotations

from app.cloudforge import constants
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

_TAGS = NodeTags(env="staging", owner="platform-team", app="analytics-exporter")
_EXPORTS_ARN = "arn:aws:s3:::customer-exports"
_RUNTIME_ARN = f"arn:aws:iam::{constants.DUMMY_ACCOUNT_ID}:role/RuntimeRole"


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
        _node("acct-main", NodeType.ACCOUNT, "staging-account", "medium"),
        _node("vpc-staging", NodeType.VPC, "staging-vpc", "low", cidr="10.0.0.0/16"),
        _node("subnet-public-a", NodeType.SUBNET, "public-a", "medium", cidr="10.0.1.0/24"),
        _node("sg-web", NodeType.SECURITY_GROUP, "web-sg", "high", ingress_cidr="0.0.0.0/0"),
        _node("cicd-github", NodeType.CICD_IDENTITY, "github-actions-oidc", "high"),
        _node("role-deploy", NodeType.IAM_ROLE, "DeployRole", "high"),
        _node("role-runtime", NodeType.IAM_ROLE, "RuntimeRole", "critical"),
        _node(
            "pol-deploy-passrole",
            NodeType.IAM_POLICY,
            "DeployPassRolePolicy",
            "high",
            actions=["iam:PassRole"],
            resource=_RUNTIME_ARN,
        ),
        _node(
            "pol-runtime-s3read",
            NodeType.IAM_POLICY,
            "RuntimeS3ReadPolicy",
            "high",
            actions=list(constants.ALLOWED_BROAD_PATTERNS),
            resource=f"{_EXPORTS_ARN}/*",
        ),
        _node(
            "s3-customer-exports",
            NodeType.S3_BUCKET,
            "customer-exports",
            "critical",
            logging="disabled",
        ),
        _node(
            "s3-public-assets",
            NodeType.S3_BUCKET,
            "public-assets",
            "medium",
            compensating_control="true",
        ),
        _node("app-analytics-exporter", NodeType.APPLICATION, "analytics-exporter", "medium"),
        _node("data-customer-exports", NodeType.DATASET, "customer-export-data", "critical"),
        _node("trail-main", NodeType.LOG_TRAIL, "main-trail", "medium"),
    ]


def _build_edges() -> list[GraphEdge]:
    return [
        _edge("cicd-github", "role-deploy", EdgeType.ASSUMES, "high"),
        _edge("role-deploy", "pol-deploy-passrole", EdgeType.ATTACHED_POLICY, "high"),
        _edge("role-deploy", "role-runtime", EdgeType.CAN_PASS_ROLE, "critical"),
        _edge("role-runtime", "pol-runtime-s3read", EdgeType.ATTACHED_POLICY, "high"),
        _edge("role-runtime", "s3-customer-exports", EdgeType.CAN_READ, "critical"),
        _edge(
            "s3-customer-exports",
            "data-customer-exports",
            EdgeType.STORES_SENSITIVE_DATA,
            "critical",
        ),
        _edge("app-analytics-exporter", "cicd-github", EdgeType.DEPLOYED_BY, "medium"),
        _edge("s3-customer-exports", "app-analytics-exporter", EdgeType.BELONGS_TO_APP, "low"),
        _edge("sg-web", "subnet-public-a", EdgeType.EXPOSED_TO_INTERNET, "high"),
        _edge("subnet-public-a", "app-analytics-exporter", EdgeType.BELONGS_TO_APP, "low"),
        _edge("s3-public-assets", "subnet-public-a", EdgeType.EXPOSED_TO_INTERNET, "low"),
        # NOTE: no `s3-customer-exports -> logs_to -> trail-main` edge — the *absence*
        # is the s3_logging_missing finding.
    ]


def build_graph() -> ScenarioGraph:
    return ScenarioGraph(nodes=_build_nodes(), edges=_build_edges())


def build_ground_truth() -> GroundTruthPaths:
    critical = GroundTruthPath(
        id="path-critical-01",
        severity="critical",
        nodes=[
            "cicd-github",
            "role-deploy",
            "role-runtime",
            "s3-customer-exports",
            "data-customer-exports",
        ],
        edges=[
            "cicd-github->assumes->role-deploy",
            "role-deploy->can_pass_role->role-runtime",
            "role-runtime->can_read->s3-customer-exports",
            "s3-customer-exports->stores_sensitive_data->data-customer-exports",
        ],
        explanation=(
            "GitHub Actions OIDC assumes DeployRole; DeployRole can iam:PassRole "
            "RuntimeRole; RuntimeRole holds broad s3:Get*/List* on the sensitive "
            "customer-exports bucket -> full read of customer data via CI."
        ),
    )
    return GroundTruthPaths(paths=[critical])


def build_findings() -> ExpectedFindings:
    return ExpectedFindings(
        findings=[_passrole(), _excessive(), _logging(), _sg(), _false_positive()]
    )


def _passrole() -> ExpectedFinding:
    return ExpectedFinding(
        id="find-passrole-01",
        severity="critical",
        family=FindingFamily.IAM_PASSROLE_RISK,
        resource_ids=["role-deploy", "role-runtime", "pol-deploy-passrole"],
        expected_scanner_visibility="partial",
        ground_truth="DeployRole can pass RuntimeRole, completing the CI-to-data chain.",
        remediation="Scope iam:PassRole to the exact RuntimeRole ARN and add a role condition.",
    )


def _excessive() -> ExpectedFinding:
    return ExpectedFinding(
        id="find-s3read-01",
        severity="high",
        family=FindingFamily.IAM_EXCESSIVE_PRIVILEGE,
        resource_ids=["role-runtime", "pol-runtime-s3read", "s3-customer-exports"],
        expected_scanner_visibility="visible",
        ground_truth="RuntimeRole has broader S3 read than intended over the exports bucket.",
        remediation="Replace s3:Get*/List* wildcards with least-privilege object prefixes.",
    )


def _logging() -> ExpectedFinding:
    return ExpectedFinding(
        id="find-logging-01",
        severity="medium",
        family=FindingFamily.S3_LOGGING_MISSING,
        resource_ids=["s3-customer-exports", "trail-main"],
        expected_scanner_visibility="visible",
        ground_truth="The sensitive bucket has no access logging / CloudTrail data events.",
        remediation="Enable S3 access logging and CloudTrail data events for the bucket.",
    )


def _sg() -> ExpectedFinding:
    return ExpectedFinding(
        id="find-sg-01",
        severity="medium",
        family=FindingFamily.SECURITY_GROUP_OVEREXPOSED,
        resource_ids=["sg-web", "subnet-public-a"],
        expected_scanner_visibility="visible",
        ground_truth="web-sg allows ingress from 0.0.0.0/0.",
        remediation="Restrict ingress from 0.0.0.0/0 to known corporate/CI CIDRs.",
    )


def _false_positive() -> ExpectedFinding:
    return ExpectedFinding(
        id="find-fp-01",
        severity="low",
        family=FindingFamily.PUBLIC_LOOKING_BUCKET_WITH_COMPENSATING_CONTROL,
        resource_ids=["s3-public-assets"],
        expected_scanner_visibility="visible",
        ground_truth="benign",
        remediation=(
            "None needed — public read is intentional; a bucket policy limits it to GetObject."
        ),
    )
