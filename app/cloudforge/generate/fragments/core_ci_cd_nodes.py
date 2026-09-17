"""Node/edge builders for ``core.ci_cd_iam_chain`` — split out to respect the
30-line function / 200-line module limits (rules/general.md).
"""

from __future__ import annotations

from app.cloudforge import constants
from app.cloudforge.models.graph import (
    EdgeSecurity,
    EdgeType,
    GraphEdge,
    GraphNode,
    NodeSecurity,
    NodeTags,
    NodeType,
)

TAGS = NodeTags(env="staging", owner="platform-team", app="analytics-exporter")
EXPORTS_ARN = "arn:aws:s3:::customer-exports"


def node(
    ns: str, node_id: str, node_type: NodeType, name: str, crit: str, **attrs: str | list[str]
) -> GraphNode:
    return GraphNode(
        id=f"{ns}/{node_id}",
        type=node_type,
        name=name,
        tags=TAGS,
        security=NodeSecurity(criticality=crit),
        attributes=dict(attrs),
    )


def edge(ns: str, src: str, dst: str, edge_type: EdgeType, risk: str) -> GraphEdge:
    return GraphEdge(
        from_=f"{ns}/{src}",
        to=f"{ns}/{dst}",
        type=edge_type,
        security=EdgeSecurity(risk=risk),
    )


def runtime_arn() -> str:
    return f"arn:aws:iam::{constants.DUMMY_ACCOUNT_ID}:role/RuntimeRole"


def hop_role_id(index: int) -> str:
    return f"role-hop-{index}"


def fixed_nodes(ns: str) -> list[GraphNode]:
    return [
        node(ns, "acct-main", NodeType.ACCOUNT, "staging-account", "medium"),
        node(ns, "vpc-staging", NodeType.VPC, "staging-vpc", "low", cidr="10.0.0.0/16"),
        node(ns, "subnet-public-a", NodeType.SUBNET, "public-a", "medium", cidr="10.0.1.0/24"),
        node(ns, "sg-web", NodeType.SECURITY_GROUP, "web-sg", "high", ingress_cidr="0.0.0.0/0"),
        node(ns, "cicd-github", NodeType.CICD_IDENTITY, "github-actions-oidc", "high"),
        node(ns, "role-deploy", NodeType.IAM_ROLE, "DeployRole", "high"),
        node(ns, "role-runtime", NodeType.IAM_ROLE, "RuntimeRole", "critical"),
        node(
            ns,
            "pol-deploy-passrole",
            NodeType.IAM_POLICY,
            "DeployPassRolePolicy",
            "high",
            actions=["iam:PassRole"],
            resource=runtime_arn(),
        ),
        node(
            ns,
            "pol-runtime-s3read",
            NodeType.IAM_POLICY,
            "RuntimeS3ReadPolicy",
            "high",
            actions=list(constants.ALLOWED_BROAD_PATTERNS),
            resource=f"{EXPORTS_ARN}/*",
        ),
        node(
            ns,
            "s3-customer-exports",
            NodeType.S3_BUCKET,
            "customer-exports",
            "critical",
            logging="disabled",
        ),
        node(
            ns,
            "s3-public-assets",
            NodeType.S3_BUCKET,
            "public-assets",
            "medium",
            compensating_control="true",
        ),
        node(ns, "app-analytics-exporter", NodeType.APPLICATION, "analytics-exporter", "medium"),
        node(
            ns,
            "data-customer-exports",
            NodeType.DATASET,
            "customer-export-data",
            "critical",
            classification="restricted",
        ),
        node(ns, "trail-main", NodeType.LOG_TRAIL, "main-trail", "medium"),
    ]


def hop_nodes(ns: str, extra: int) -> list[GraphNode]:
    return [
        node(ns, hop_role_id(i), NodeType.IAM_ROLE, f"IntermediateRole{i}", "high")
        for i in range(extra)
    ]


def pass_role_chain(ns: str, extra: int) -> list[GraphEdge]:
    """``role-deploy --can_pass_role--> ... hops ... --can_pass_role--> role-runtime``."""
    chain = ["role-deploy", *[hop_role_id(i) for i in range(extra)], "role-runtime"]
    return [
        edge(ns, chain[i], chain[i + 1], EdgeType.CAN_PASS_ROLE, "critical")
        for i in range(len(chain) - 1)
    ]


def fixed_edges(ns: str) -> list[GraphEdge]:
    return [
        edge(ns, "cicd-github", "role-deploy", EdgeType.ASSUMES, "high"),
        edge(ns, "role-deploy", "pol-deploy-passrole", EdgeType.ATTACHED_POLICY, "high"),
        edge(ns, "role-runtime", "pol-runtime-s3read", EdgeType.ATTACHED_POLICY, "high"),
        edge(ns, "role-runtime", "s3-customer-exports", EdgeType.CAN_READ, "critical"),
        edge(
            ns,
            "s3-customer-exports",
            "data-customer-exports",
            EdgeType.STORES_SENSITIVE_DATA,
            "critical",
        ),
        edge(ns, "app-analytics-exporter", "cicd-github", EdgeType.DEPLOYED_BY, "medium"),
        edge(ns, "s3-customer-exports", "app-analytics-exporter", EdgeType.BELONGS_TO_APP, "low"),
        edge(ns, "sg-web", "subnet-public-a", EdgeType.EXPOSED_TO_INTERNET, "high"),
        edge(ns, "subnet-public-a", "app-analytics-exporter", EdgeType.BELONGS_TO_APP, "low"),
        edge(ns, "s3-public-assets", "subnet-public-a", EdgeType.EXPOSED_TO_INTERNET, "low"),
        # NOTE: no `s3-customer-exports -> logs_to -> trail-main` edge — the
        # *absence* is the s3_logging_missing finding.
    ]
