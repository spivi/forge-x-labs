"""RiskPattern-side enums for the learning-corpus ontology (design §6).

Extracted from ``pattern_models.py`` to keep each module within the 200-line cap
(rules/general.md). These are the pattern classification/vocabulary enums;
``ReuseStatus`` / ``SourceType`` live in ``source_models.py``. ``pattern_models`` imports
and re-exports every name here, so callers may import from either module.
"""

from __future__ import annotations

from enum import StrEnum


class CloudProvider(StrEnum):
    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"
    KUBERNETES = "kubernetes"
    MULTI_CLOUD = "multi_cloud"
    GENERIC = "generic"


class Domain(StrEnum):
    IAM = "iam"
    STORAGE = "storage"
    NETWORK = "network"
    LOGGING = "logging"
    ENCRYPTION = "encryption"
    CI_CD = "ci_cd"
    SECRETS = "secrets"
    DATA = "data"
    COMPUTE = "compute"
    DATABASE = "database"
    SERVERLESS = "serverless"
    CONTAINERS = "containers"
    MONITORING = "monitoring"
    GOVERNANCE = "governance"


class WeaknessFamily(StrEnum):
    """cloudforge families (mirroring ``findings.FindingFamily``) plus a generic list.

    The first six values are kept identical to ``models.findings.FindingFamily`` so a
    weakness family and a finding family share a vocabulary; the rest are the generic,
    provider-agnostic families from design §6.
    """

    # cloudforge families (aligned with FindingFamily).
    IAM_EXCESSIVE_PRIVILEGE = "iam_excessive_privilege"
    IAM_PASSROLE_RISK = "iam_passrole_risk"
    S3_LOGGING_MISSING = "s3_logging_missing"
    S3_PUBLIC_EXPOSURE = "s3_public_exposure"
    SECURITY_GROUP_OVEREXPOSED = "security_group_overexposed"
    PUBLIC_LOOKING_BUCKET_WITH_COMPENSATING_CONTROL = (
        "public_looking_bucket_with_compensating_control"
    )
    # generic, provider-agnostic families.
    PUBLIC_EXPOSURE = "public_exposure"
    EXCESSIVE_PRIVILEGE = "excessive_privilege"
    MISSING_ENCRYPTION = "missing_encryption"
    MISSING_LOGGING = "missing_logging"
    WEAK_NETWORK_BOUNDARY = "weak_network_boundary"
    INSECURE_DEFAULTS = "insecure_defaults"
    SECRETS_EXPOSURE = "secrets_exposure"
    UNRESTRICTED_ACCESS = "unrestricted_access"
    MISCONFIGURED_CONTROL = "misconfigured_control"
    OTHER = "other"


class SafetyClassification(StrEnum):
    DEFENSIVE_PATTERN = "defensive_pattern"
    BENCHMARK_PATTERN = "benchmark_pattern"
    TRAINING_PATTERN = "training_pattern"
    RESTRICTED_SOURCE = "restricted_source"
    UNSAFE_OPERATIONAL = "unsafe_operational"
    UNKNOWN = "unknown"


class ValidationStatus(StrEnum):
    UNVALIDATED = "unvalidated"
    VALID = "valid"
    INVALID = "invalid"


# Classifications that may be exported for training (design §6/§9.6).
TRAINABLE_CLASSIFICATIONS: frozenset[SafetyClassification] = frozenset(
    {
        SafetyClassification.DEFENSIVE_PATTERN,
        SafetyClassification.BENCHMARK_PATTERN,
        SafetyClassification.TRAINING_PATTERN,
    }
)
