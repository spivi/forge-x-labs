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
    # (stem, bucket name, trail name, data set): a bucket wired to its own
    # access-log trail and the data it holds behind that control
    ("app-config", "app-config-store", "trail-app-config", "app-config-values"),
    ("ops-runbooks", "ops-runbooks", "trail-ops-runbooks", "runbook-library"),
    ("billing-exports", "billing-exports-archive", "trail-billing-exports", "billing-statements"),
    ("audit-evidence", "audit-evidence", "trail-audit-evidence", "audit-evidence-files"),
    ("ml-features", "ml-feature-store", "trail-ml-features", "feature-vectors"),
    ("partner-uploads", "partner-uploads", "trail-partner-uploads", "partner-upload-files"),
)

# Every data set carries one of these, drawn with the fragment rng, so the core
# sink is neither the only labeled data set nor the only one at its level. A
# compensating control always guards a ``restricted`` set: that is what makes it
# worth a control, and it keeps "find the restricted one" from being the answer.
CLASSIFICATIONS = ("public", "internal", "confidential", "restricted")
SINK_CLASSIFICATION = "restricted"

# --- Azure non-core vocabulary -------------------------------------------------
# Same rule as above: nothing says what the fragment is for. Storage account names
# are the 3-24 lowercase alphanumerics azurerm accepts; key vault names stay under
# 18 characters so the composer's ``-N`` dedupe and ``-<salt>`` suffixes fit in 24.

AZURE_LOG_CONTAINERS = (
    # (container name, storage account)
    ("cnt-app-logs", "stapplogs"),
    ("cnt-web-logs", "stweblogs"),
    ("cnt-func-logs", "stfunclogs"),
    ("cnt-diag-logs", "stdiaglogs"),
    ("cnt-ingest-logs", "stingestlogs"),
)

AZURE_CONFIG_VAULTS = (
    "kv-app-config",
    "kv-web-config",
    "kv-tls-certs",
    "kv-build-signing",
    "kv-ops-tooling",
)

AZURE_IDENTITY_NAMES = (
    "id-monitoring-agent",
    "id-metrics-collector",
    "id-log-forwarder",
    "id-health-probe",
    "id-backup-runner",
)

AZURE_APP_NAMES = (
    "app-internal-wiki",
    "app-ops-dashboard",
    "app-status-page",
    "app-admin-portal",
    "app-release-notes",
)

AZURE_RESOURCE_GROUPS = (
    "rg-monitoring",
    "rg-shared-tools",
    "rg-network-hub",
    "rg-build-agents",
    "rg-sandbox-a",
)

AZURE_DECOY_IDENTITIES = (
    # (identity name, container name, storage account): an identity whose only
    # grant reaches a container that holds nothing sensitive
    ("id-reporting-reader", "cnt-report-exports", "streportexports"),
    ("id-partner-sync", "cnt-partner-inbox", "stpartnerinbox"),
    ("id-qa-fixtures", "cnt-qa-fixtures", "stqafixtures"),
    ("id-migration-helper", "cnt-migration-staging", "stmigration"),
    ("id-release-audit", "cnt-release-archive", "streleasearchive"),
)

AZURE_PUBLIC_LOOKING_CONTAINERS = (
    # (container name, storage account): containers an operator would really serve
    ("cnt-static-site", "ststaticsite"),
    ("cnt-public-docs", "stpublicdocs"),
    ("cnt-cdn-origin", "stcdnorigin"),
    ("cnt-marketing-downloads", "stmarketing"),
    ("cnt-open-data", "stopendata"),
    ("cnt-release-downloads", "streleasedl"),
)

AZURE_LOCKED_VAULTS = (
    # (vault, container the vault's key opens, storage account, data set)
    ("kv-billing-keys", "cnt-billing-statements", "stbilling", "billing-statements"),
    ("kv-signing-keys", "cnt-release-signing", "stsigning", "release-signatures"),
    ("kv-db-creds", "cnt-db-backups", "stdbbackups", "db-backup-sets"),
    ("kv-partner-certs", "cnt-partner-contracts", "stpartner", "partner-contracts"),
    ("kv-backup-keys", "cnt-backup-vault", "stbackupvault", "backup-archives"),
)

AZURE_DATA_CONTAINERS = (
    # (container, storage account, data set): a container and the data it holds
    ("cnt-analytics-cache", "stanalytics", "analytics-cache"),
    ("cnt-reporting-store", "streporting", "reporting-store"),
    ("cnt-telemetry-sink", "sttelemetry", "telemetry-sink"),
    ("cnt-ops-metrics", "stopsmetrics", "operational-metrics"),
    ("cnt-media-cache", "stmedia", "media-cache"),
)

# --- GCP non-core vocabulary ---------------------------------------------------
# Service-account and pool names must be lowercase letters, digits and hyphens
# and fit the 30/32 character ids the emitter derives from them after the salt.

GCP_ARTIFACT_BUCKETS = (
    "bkt-build-artifacts",
    "bkt-ci-cache",
    "bkt-release-images",
    "bkt-test-reports",
    "bkt-docker-layers",
)

GCP_CI_SERVICE_ACCOUNTS = (
    "sa-ci-runner",
    "sa-build-agent",
    "sa-test-runner",
    "sa-release-bot",
    "sa-lint-worker",
)

GCP_PROJECTS = (
    # (project name, project id)
    ("prj-shared-tools", "prj-shared-tools-201"),
    ("prj-sandbox-dev", "prj-sandbox-dev-202"),
    ("prj-ci-builders", "prj-ci-builders-203"),
    ("prj-monitoring", "prj-monitoring-204"),
    ("prj-network-hub", "prj-network-hub-205"),
)

GCP_FOLDERS = (
    "fld-shared-services",
    "fld-sandboxes",
    "fld-platform",
    "fld-data-eng",
    "fld-partners",
)

GCP_PARTNER_POOLS = (
    # (pool name, issuer uri): a workload identity pool for a partner's CI
    ("pool-partner-ci", "https://gitlab.com"),
    ("pool-vendor-builds", "https://token.actions.githubusercontent.com"),
    ("pool-tfc-runs", "https://app.terraform.io"),
    ("pool-bitbucket-ci", "https://bitbucket.org"),
)

GCP_DECOY_BINDINGS = (
    # (service account, bucket): a viewer binding on a bucket with no sensitive data
    ("sa-reporting-reader", "bkt-report-exports"),
    ("sa-partner-sync", "bkt-partner-inbox"),
    ("sa-qa-fixtures", "bkt-qa-fixtures"),
    ("sa-migration-helper", "bkt-migration-staging"),
    ("sa-release-audit", "bkt-release-archive"),
)

GCP_PUBLIC_LOOKING_BUCKETS = (
    "bkt-static-site",
    "bkt-public-docs",
    "bkt-cdn-origin",
    "bkt-marketing-downloads",
    "bkt-open-data",
    "bkt-release-downloads",
)

GCP_LOCKED_BUCKETS = (
    # (bucket, data set it holds behind public access prevention)
    ("bkt-billing-exports", "billing-statements"),
    ("bkt-audit-evidence", "audit-evidence-files"),
    ("bkt-ml-features", "feature-vectors"),
    ("bkt-partner-uploads", "partner-upload-files"),
    ("bkt-ops-runbooks", "runbook-library"),
)

GCP_DATA_BUCKETS = (
    # (bucket, data set): a bucket and the data it holds
    ("bkt-analytics-cache", "analytics-cache"),
    ("bkt-reporting-store", "reporting-store"),
    ("bkt-telemetry-sink", "telemetry-sink"),
    ("bkt-ops-metrics", "operational-metrics"),
    ("bkt-media-cache", "media-cache"),
)

# --- Kubernetes non-core vocabulary --------------------------------------------

K8S_NAMESPACE_PODS = (
    # (namespace, pod)
    ("batch-jobs", "nightly-report"),
    ("monitoring", "metrics-agent"),
    ("ingress-system", "edge-proxy"),
    ("ci-runners", "build-worker"),
    ("cache", "cache-proxy"),
)

K8S_PLAIN_SERVICE_ACCOUNTS = (
    # service accounts with no cloud annotation at all
    "metrics-reader",
    "log-shipper",
    "cert-renewer",
    "backup-agent",
    "queue-consumer",
)

K8S_CLUSTERS = (
    # (cluster name, oidc issuer): a second cluster next to the one on the path
    ("eks-tools-cluster", "https://oidc.eks.us-east-1.amazonaws.com/id/EXAMPLE1A2B3C4D5E6F7A8B9"),
    (
        "eks-staging-cluster",
        "https://oidc.eks.us-east-1.amazonaws.com/id/EXAMPLE2B3C4D5E6F7A8B9C0",
    ),
    (
        "eks-sandbox-cluster",
        "https://oidc.eks.us-west-2.amazonaws.com/id/EXAMPLE3C4D5E6F7A8B9C0D1",
    ),
    ("eks-batch-cluster", "https://oidc.eks.eu-west-1.amazonaws.com/id/EXAMPLE4D5E6F7A8B9C0D1E2"),
)

K8S_DATA_PODS = (
    # (pod, data set): a stateful pod in the workloads namespace and what it holds
    ("postgres-primary", "orders-db"),
    ("redis-cache", "session-cache"),
    ("minio-gateway", "build-cache"),
    ("elastic-data", "search-index"),
    ("kafka-broker", "event-log"),
)

K8S_BARE_NAMESPACES = (
    "cert-manager",
    "kube-metrics",
    "logging",
    "dev-sandbox",
    "argo-events",
)

K8S_DECOY_BINDINGS = (
    # (service account, IAM role name, the role's actions): an annotated service
    # account whose role can do operational things but reaches no data
    ("metrics-exporter", "MetricsExportRole", ("cloudwatch:PutMetricData", "logs:PutLogEvents")),
    ("cost-reporter", "CostReportRole", ("ce:GetCostAndUsage", "ce:GetCostForecast")),
    (
        "node-autoscaler",
        "AutoscalerRole",
        ("autoscaling:DescribeAutoScalingGroups", "autoscaling:SetDesiredCapacity"),
    ),
    (
        "external-dns",
        "ExternalDnsRole",
        ("route53:ListHostedZones", "route53:ListResourceRecordSets"),
    ),
)
