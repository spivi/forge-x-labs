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
