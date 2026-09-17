"""Ground truth: the expected findings and the intended risk paths.

These are authored alongside the graph so the risk engine can prove the generated
scenario actually contains the risks it claims to.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from app.cloudforge.models.graph import NodeType

ScannerVisibility = Literal["visible", "partial", "invisible"]
Severity = Literal["low", "medium", "high", "critical"]


class FindingFamily(StrEnum):
    IAM_EXCESSIVE_PRIVILEGE = "iam_excessive_privilege"
    IAM_PASSROLE_RISK = "iam_passrole_risk"
    IAM_CROSS_ACCOUNT_TRUST = "iam_cross_account_trust"
    IAM_PRIVESC_POLICY_VERSION = "iam_privesc_policy_version"
    EC2_IMDSV1_ENABLED = "ec2_imdsv1_enabled"
    LAMBDA_FUNCTION_URL_UNAUTHENTICATED = "lambda_function_url_unauthenticated"
    SECRETSMANAGER_POLICY_OVERBROAD = "secretsmanager_policy_overbroad"
    RDS_INSTANCE_PUBLIC = "rds_instance_public"
    ECR_REPOSITORY_PUBLIC_READ = "ecr_repository_public_read"
    SQS_QUEUE_POLICY_OVERBROAD = "sqs_queue_policy_overbroad"
    S3_LOGGING_MISSING = "s3_logging_missing"
    S3_PUBLIC_EXPOSURE = "s3_public_exposure"
    KMS_KEY_POLICY_OVERBROAD = "kms_key_policy_overbroad"
    EBS_SNAPSHOT_PUBLIC = "ebs_snapshot_public"
    SECURITY_GROUP_OVEREXPOSED = "security_group_overexposed"
    PUBLIC_LOOKING_BUCKET_WITH_COMPENSATING_CONTROL = (
        "public_looking_bucket_with_compensating_control"
    )
    K8S_POD_IRSA_EXFIL = "k8s_pod_irsa_exfil"
    AZURE_IMDS_KEYVAULT_HARVEST = "azure_imds_keyvault_harvest"
    GCP_WORKLOAD_IDENTITY_FEDERATION = "gcp_workload_identity_federation"


class SinkKind(StrEnum):
    """What the attacker reaches at the end of a path: the type of its ``target``."""

    DATA = "data"
    SECRET = "secret"
    KEY = "key"
    ROLE = "role"
    IMAGE = "image"
    QUEUE = "queue"
    SNAPSHOT = "snapshot"
    DATABASE = "database"
    VAULT = "vault"


# The node types a path of each ``sink_kind`` may end on. The composer refuses a
# fragment whose declared target is not the last node or has another type.
SINK_NODE_TYPES: dict[SinkKind, frozenset[NodeType]] = {
    SinkKind.DATA: frozenset({NodeType.DATASET}),
    SinkKind.SECRET: frozenset({NodeType.SECRETS_MANAGER_SECRET}),
    SinkKind.KEY: frozenset({NodeType.KMS_KEY}),
    SinkKind.ROLE: frozenset({NodeType.IAM_ROLE}),
    SinkKind.IMAGE: frozenset({NodeType.ECR_REPOSITORY}),
    SinkKind.QUEUE: frozenset({NodeType.SQS_QUEUE}),
    SinkKind.SNAPSHOT: frozenset({NodeType.EBS_SNAPSHOT}),
    SinkKind.DATABASE: frozenset({NodeType.RDS_INSTANCE}),
    SinkKind.VAULT: frozenset({NodeType.AZURE_KEY_VAULT}),
}


class ExpectedFinding(BaseModel):
    """One labeled finding a scanner may or may not detect."""

    model_config = ConfigDict(extra="forbid")

    id: str
    severity: Severity
    family: FindingFamily
    resource_ids: list[str]
    expected_scanner_visibility: ScannerVisibility
    ground_truth: str
    remediation: str


class ExpectedFindings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    findings: list[ExpectedFinding]


class GroundTruthPath(BaseModel):
    """An intended risk path through the graph (node + edge id sequence).

    ``target`` is the node the attacker reaches (the sink) and ``sink_kind`` says
    what kind of thing that is. A pack written before these fields existed still
    loads: ``target`` defaults to the last node and ``sink_kind`` to ``data``.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    severity: Severity
    nodes: list[str]
    edges: list[str]
    explanation: str
    sink_kind: SinkKind = SinkKind.DATA
    target: str = ""

    @model_validator(mode="after")
    def _target_defaults_to_the_last_node(self) -> GroundTruthPath:
        if not self.target and self.nodes:
            self.target = self.nodes[-1]
        return self


class GroundTruthPaths(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paths: list[GroundTruthPath]
