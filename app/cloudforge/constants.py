"""Central constants — no magic strings or numbers elsewhere in the package.

Filenames, artifact-tree layout, severity/visibility vocab, the forbidden and
allowed IAM permission patterns for the risk engine, and the mandatory local-only
banner all live here so they are defined exactly once.
"""

from __future__ import annotations

from typing import Final

# --- artifact filenames (the output-tree contract) ---------------------------
SCENARIO_FILENAME: Final = "scenario.yaml"
GRAPH_FILENAME: Final = "graph.json"
EXPECTED_FINDINGS_FILENAME: Final = "expected_findings.json"
GROUND_TRUTH_FILENAME: Final = "ground_truth_paths.json"
OPA_RESULTS_FILENAME: Final = "opa_results.json"
SCANNER_SCORE_FILENAME: Final = "scanner_score.json"
REPORT_FILENAME: Final = "report.md"
TERRAFORM_DIRNAME: Final = "terraform"
SCANNER_RESULTS_DIRNAME: Final = "scanner_results"
CHECKOV_RESULTS_FILENAME: Final = "checkov.json"

TERRAFORM_FILES: Final = (
    "providers.tf",
    "variables.tf",
    "main.tf",
    "iam.tf",
    "s3.tf",
    "network.tf",
    "kms.tf",
    "snapshot.tf",
    "compute.tf",
    "serverless.tf",
    "database.tf",
    "services.tf",
    "azure.tf",
    "gcp.tf",
    "k8s.tf",
)

# --- safe fake values (never deployed) ---------------------------------------
DUMMY_ACCOUNT_ID: Final = "000000000000"
EXTERNAL_DUMMY_ACCOUNT_ID: Final = "999999999999"
DUMMY_VOLUME_ID: Final = "vol-00000000"
DEFAULT_REGION: Final = "us-east-1"

# --- terraform emitter defaults ----------------------------------------------
# The scenario graph declares the ingress CIDR (the modeled risk); the port is not
# part of any finding, so the emitter renders a fixed HTTPS port for every SG.
DEFAULT_INGRESS_PORT: Final = 443
# Header for a ``.tf`` file whose node type is absent for a family. Keeps the file
# present and ``terraform validate``-clean without emitting stray resources.
EMPTY_TF_HEADER: Final = "# No resources of this kind in this scenario family.\n"

# --- forbidden destructive permissions (risk engine rejects these) -----------
# Broad read/list is intentionally allowed (it is the modeled misconfiguration);
# destructive actions are never valid in a generated scenario.
FORBIDDEN_PERMISSION_PATTERNS: Final = (
    "iam:Delete*",
    "s3:DeleteBucket",
    "ec2:TerminateInstances",
    "kms:ScheduleKeyDeletion",
    "organizations:*",
)

# Broad grants that ARE allowed but must be documented by an expected finding.
ALLOWED_BROAD_PATTERNS: Final = (
    "s3:Get*",
    "s3:List*",
    "iam:CreatePolicyVersion",
    "iam:SetDefaultPolicyVersion",
    "ecr:BatchGetImage",
    "ecr:GetDownloadUrlForLayer",
    "sqs:ReceiveMessage",
    "sqs:SendMessage",
    "secretsmanager:GetSecretValue",
)

# --- required report banner --------------------------------------------------
LOCAL_ONLY_BANNER: Final = (
    "This scenario is generated for local static analysis, scanner benchmarking, "
    "and defensive security training. It is not deployed and does not require "
    "cloud credentials."
)

# --- learning-corpus CLI default paths (design §10) ---------------------------
SOURCE_REGISTRY_PATH: Final = "data/source_registry.yaml"
RAW_SOURCES_DIRNAME: Final = "data/raw"
CORPUS_JSONL_PATH: Final = "data/corpus.jsonl"
TRAINING_EXPORT_DIRNAME: Final = "training_export"
