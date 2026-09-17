"""Fixed benign vocabulary shared by non-core fragments.

Mirrors the pattern in ``generate/mutation_ops.py`` — tag/name values are drawn
from fixed tuples only (never free text), so a fragment can never smuggle a
real secret or an unexpected value into a generated scenario.
"""

from __future__ import annotations

ENV_VALUES = ("staging", "stage", "preprod", "test", "sandbox", "internal")
OWNER_VALUES = (
    "platform-team",
    "infra-team",
    "sre-team",
    "devops-crew",
    "cloud-eng",
    "secops-team",
    "data-eng",
)
APP_VALUES = (
    "analytics-exporter",
    "data-exporter",
    "report-pipeline",
    "etl-runner",
    "billing-sync",
    "telemetry-worker",
)

BUCKET_NAMES = (
    "assets-archive",
    "telemetry-logs",
    "build-artifacts",
    "exports-staging",
    "media-cache",
    "backup-vault",
)

QUEUE_NAMES = (
    "audit-events",
    "jobs-dispatch",
    "notifications-stream",
    "ingest-pipeline",
    "metrics-queue",
)

SUBNET_NAMES = (
    "subnet-private-b",
    "subnet-worker-c",
    "subnet-db-internal",
    "subnet-analytics-dmz",
    "subnet-services-a",
)

ROLE_NAMES = (
    "DatadogMonitoringRole",
    "PrometheusAgentRole",
    "BackupRunnerRole",
    "MetricsCollectorRole",
    "CloudWatchAgentRole",
)

LAMBDA_NAMES = (
    "log-compactor",
    "snapshot-cleaner",
    "metric-pusher",
    "health-prober",
    "cache-invalidator",
)

DATA_NAMES = (
    "data-analytics-cache",
    "data-operational-metrics",
    "data-telemetry-sink",
    "data-reporting-store",
)

TRAIL_NAMES = (
    "trail-security-secondary",
    "trail-audit-operations",
    "trail-infra-events",
)

KMS_NAMES = (
    "kms-storage-general",
    "kms-app-configs",
    "kms-internal-telemetry",
)

SG_NAMES = (
    "sg-internal-workers",
    "sg-database-clients",
    "sg-monitoring-agents",
    "sg-infra-management",
)

ECR_NAMES = (
    "repo-base-runner",
    "repo-analytics-worker",
    "repo-collector-agent",
    "repo-utility-image",
)

# Identities for the non-core fragments. Nothing below may say what the fragment
# is for (decoy, noise, false positive, control): node ids and names reach the
# student estate, and a role word in either hands over the answer key. Each entry
# is a tuple so one draw yields a slug plus names that belong together.

DECOY_IDENTITIES = (
    # (stem, role name, policy name, scratch bucket the policy points at)
    ("legacy-support", "LegacySupportRole", "LegacySupportReadPolicy", "legacy-support-scratch"),
    ("reporting-read", "ReportingReadRole", "ReportingReadPolicy", "reporting-exports-scratch"),
    ("qa-automation", "QaAutomationRole", "QaAutomationReadPolicy", "qa-automation-fixtures"),
    ("migration-helper", "MigrationHelperRole", "MigrationHelperReadPolicy", "migration-staging"),
    ("partner-sync", "PartnerSyncRole", "PartnerSyncReadPolicy", "partner-sync-inbox"),
    ("release-audit", "ReleaseAuditRole", "ReleaseAuditReadPolicy", "release-audit-archive"),
)

PUBLIC_LOOKING_BUCKETS = (
    # (stem, bucket name): buckets an operator would really open to the internet
    ("static-site", "static-site-assets"),
    ("public-docs", "public-docs-mirror"),
    ("cdn-origin", "cdn-origin-media"),
    ("marketing-downloads", "marketing-downloads"),
    ("open-data", "open-data-exports"),
    ("release-downloads", "release-downloads"),
)

LOGGED_BUCKETS = (
    # (stem, bucket name, trail name): a bucket wired to its own access-log trail
    ("app-config", "app-config-store", "trail-app-config"),
    ("ops-runbooks", "ops-runbooks", "trail-ops-runbooks"),
    ("billing-exports", "billing-exports-archive", "trail-billing-exports"),
    ("audit-evidence", "audit-evidence", "trail-audit-evidence"),
    ("ml-features", "ml-feature-store", "trail-ml-features"),
    ("partner-uploads", "partner-uploads", "trail-partner-uploads"),
)
