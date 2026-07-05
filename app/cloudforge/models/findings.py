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
    S3_LOGGING_MISSING = "s3_logging_missing"
    S3_PUBLIC_EXPOSURE = "s3_public_exposure"
    SECURITY_GROUP_OVEREXPOSED = "security_group_overexposed"
    PUBLIC_LOOKING_BUCKET_WITH_COMPENSATING_CONTROL = (
        "public_looking_bucket_with_compensating_control"
    )


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
