"""Ground truth: the expected findings and the intended risk paths.

These are authored alongside the graph so the risk engine can prove the generated
scenario actually contains the risks it claims to.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict

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
    """An intended risk path through the graph (node + edge id sequence)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    severity: Severity
    nodes: list[str]
    edges: list[str]
    explanation: str


class GroundTruthPaths(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paths: list[GroundTruthPath]
