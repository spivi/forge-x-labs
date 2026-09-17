"""Node/edge builders for ``core.ci_cd_iam_chain``, split out to keep the story
module short. The chain's shape (hop count, dead end) comes from the composer's
params through ``_core.shape_of``; this module only knows how to mint the pieces.
"""

from __future__ import annotations

from random import Random

from app.cloudforge import constants
from app.cloudforge.generate.fragments._core import Hops, Kit, draw_hops
from app.cloudforge.generate.fragments._vocab import AWS_HOP_ROLES
from app.cloudforge.models.graph import EdgeType, GraphEdge, GraphNode, NodeTags, NodeType

TAGS = NodeTags(env="staging", owner="platform-team", app="analytics-exporter")
EXPORTS_ARN = "arn:aws:s3:::customer-exports"


def runtime_arn() -> str:
    return f"arn:aws:iam::{constants.DUMMY_ACCOUNT_ID}:role/RuntimeRole"


def fixed_nodes(kit: Kit) -> list[GraphNode]:
    return [
        kit.node("acct-main", NodeType.ACCOUNT, "staging-account", "medium"),
        kit.node("vpc-staging", NodeType.VPC, "staging-vpc", "low", cidr="10.0.0.0/16"),
        kit.node("subnet-public-a", NodeType.SUBNET, "public-a", "medium", cidr="10.0.1.0/24"),
        kit.node("sg-web", NodeType.SECURITY_GROUP, "web-sg", "high", ingress_cidr="0.0.0.0/0"),
        kit.node("cicd-github", NodeType.CICD_IDENTITY, "github-actions-oidc", "high"),
        kit.node("role-deploy", NodeType.IAM_ROLE, "DeployRole", "high"),
        kit.node("role-runtime", NodeType.IAM_ROLE, "RuntimeRole", "critical"),
        kit.node(
            "pol-deploy-passrole",
            NodeType.IAM_POLICY,
            "DeployPassRolePolicy",
            "high",
            actions=["iam:PassRole"],
            resource=runtime_arn(),
        ),
        kit.node(
            "pol-runtime-s3read",
            NodeType.IAM_POLICY,
            "RuntimeS3ReadPolicy",
            "high",
            actions=list(constants.ALLOWED_BROAD_PATTERNS),
            resource=f"{EXPORTS_ARN}/*",
        ),
        kit.node(
            "s3-customer-exports",
            NodeType.S3_BUCKET,
            "customer-exports",
            "critical",
            logging="disabled",
        ),
        kit.node(
            "s3-public-assets",
            NodeType.S3_BUCKET,
            "public-assets",
            "medium",
            compensating_control="true",
        ),
        kit.node("app-analytics-exporter", NodeType.APPLICATION, "analytics-exporter", "medium"),
        kit.node(
            "data-customer-exports",
            NodeType.DATASET,
            "customer-export-data",
            "critical",
            classification="restricted",
        ),
        kit.node("trail-main", NodeType.LOG_TRAIL, "main-trail", "medium"),
    ]


def hop_nodes(kit: Kit, rng: Random, extra: int) -> Hops:
    """``extra`` intermediate roles between DeployRole and RuntimeRole."""
    return draw_hops(kit, rng, extra, AWS_HOP_ROLES, "role", NodeType.IAM_ROLE)


def pass_role_chain(kit: Kit, chain: list[str]) -> list[GraphEdge]:
    """``role-deploy --can_pass_role--> ... hops ... --can_pass_role--> role-runtime``."""
    return kit.chain(chain, EdgeType.CAN_PASS_ROLE, "critical")


def fixed_edges(kit: Kit) -> list[GraphEdge]:
    return [
        kit.edge("cicd-github", "role-deploy", EdgeType.ASSUMES, "high"),
        kit.edge("role-deploy", "pol-deploy-passrole", EdgeType.ATTACHED_POLICY, "high"),
        kit.edge("role-runtime", "pol-runtime-s3read", EdgeType.ATTACHED_POLICY, "high"),
        kit.edge("role-runtime", "s3-customer-exports", EdgeType.CAN_READ, "critical"),
        kit.edge(
            "s3-customer-exports",
            "data-customer-exports",
            EdgeType.STORES_SENSITIVE_DATA,
            "critical",
        ),
        kit.edge("app-analytics-exporter", "cicd-github", EdgeType.DEPLOYED_BY, "medium"),
        kit.edge("s3-customer-exports", "app-analytics-exporter", EdgeType.BELONGS_TO_APP, "low"),
        kit.edge("sg-web", "subnet-public-a", EdgeType.EXPOSED_TO_INTERNET, "high"),
        kit.edge("subnet-public-a", "app-analytics-exporter", EdgeType.BELONGS_TO_APP, "low"),
        kit.edge("s3-public-assets", "subnet-public-a", EdgeType.EXPOSED_TO_INTERNET, "low"),
        # NOTE: no `s3-customer-exports -> logs_to -> trail-main` edge: the
        # *absence* is the s3_logging_missing finding.
    ]
