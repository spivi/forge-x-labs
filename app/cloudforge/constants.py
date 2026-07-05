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
)

# --- safe fake values (never deployed) ---------------------------------------
DUMMY_ACCOUNT_ID: Final = "000000000000"
DEFAULT_REGION: Final = "us-east-1"

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
)

# --- required report banner --------------------------------------------------
LOCAL_ONLY_BANNER: Final = (
    "This scenario is generated for local static analysis, scanner benchmarking, "
    "and defensive security training. It is not deployed and does not require "
    "cloud credentials."
)
