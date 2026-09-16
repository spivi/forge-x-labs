"""The normalized cloud-risk graph — the source of truth for a scenario.

Terraform is compiled *from* this graph; ground-truth paths and expected findings
reference the same node/edge ids. A model-level validator guarantees every edge
endpoint resolves to a real node so downstream artifacts stay self-consistent.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Criticality = Literal["low", "medium", "high", "critical"]
EdgeRisk = Literal["none", "low", "medium", "high", "critical"]


class NodeType(StrEnum):
    ACCOUNT = "Account"
    VPC = "VPC"
    SUBNET = "Subnet"
    SECURITY_GROUP = "SecurityGroup"
    IAM_ROLE = "IAMRole"
    IAM_POLICY = "IAMPolicy"
    CICD_IDENTITY = "CICDIdentity"
    S3_BUCKET = "S3Bucket"
    KMS_KEY = "KmsKey"
    EBS_SNAPSHOT = "EbsSnapshot"
    EC2_INSTANCE = "EC2Instance"
    LAMBDA_FUNCTION = "LambdaFunction"
    SECRETS_MANAGER_SECRET = "SecretsManagerSecret"
    RDS_INSTANCE = "RdsInstance"
    ECR_REPOSITORY = "EcrRepository"
    SQS_QUEUE = "SqsQueue"
    APPLICATION = "Application"
    DATASET = "DataSet"
    LOG_TRAIL = "LogTrail"


class EdgeType(StrEnum):
    ASSUMES = "assumes"
    CAN_PASS_ROLE = "can_pass_role"
    ATTACHED_POLICY = "attached_policy"
    CAN_READ = "can_read"
    CAN_WRITE = "can_write"
    BELONGS_TO_APP = "belongs_to_app"
    STORES_SENSITIVE_DATA = "stores_sensitive_data"
    EXPOSED_TO_INTERNET = "exposed_to_internet"
    LOGS_TO = "logs_to"
    HAS_SECURITY_GROUP = "has_security_group"
    DEPLOYED_BY = "deployed_by"
    CAN_DECRYPT = "can_decrypt"
    CAN_INVOKE = "can_invoke"


class NodeTags(BaseModel):
    model_config = ConfigDict(extra="forbid")

    env: str
    owner: str
    app: str


class NodeSecurity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    criticality: Criticality


class EdgeSecurity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    risk: EdgeRisk


class GraphNode(BaseModel):
    """A single cloud resource or identity in the risk graph."""

    model_config = ConfigDict(extra="forbid")

    id: str
    type: NodeType
    name: str
    tags: NodeTags
    security: NodeSecurity
    # Terraform-relevant payload (IAM actions, CIDRs, bucket names, arns...).
    attributes: dict[str, str | list[str]] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    """A directed relationship between two graph nodes."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    from_: str = Field(alias="from")
    to: str
    type: EdgeType
    security: EdgeSecurity

    @property
    def key(self) -> str:
        """Stable edge id used by ground-truth paths: ``from->type->to``."""
        return f"{self.from_}->{self.type.value}->{self.to}"


class ScenarioGraph(BaseModel):
    """The full risk graph: nodes plus the directed edges between them."""

    model_config = ConfigDict(extra="forbid")

    nodes: list[GraphNode]
    edges: list[GraphEdge]

    @model_validator(mode="after")
    def _edges_reference_existing_nodes(self) -> ScenarioGraph:
        node_ids = {node.id for node in self.nodes}
        for edge in self.edges:
            missing = {edge.from_, edge.to} - node_ids
            if missing:
                raise ValueError(f"edge {edge.key} references unknown node(s): {sorted(missing)}")
        return self
