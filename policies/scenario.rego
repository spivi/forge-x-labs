# cloudforge scenario policy.
#
# Evaluated over graph.json (the source of truth). Terraform-plan support is future.
# `deny` collects rule violations; the validator fails if any deny message appears.
#
# Run locally (optional — skipped if `opa` is absent):
#   opa eval -i out/scenario_001/graph.json -d policies/scenario.rego \
#     "data.cloudforge.deny" --format json

package cloudforge

import rego.v1

# --- forbidden destructive permissions ---------------------------------------
forbidden_patterns := ["iam:Delete", "s3:DeleteBucket", "ec2:TerminateInstances", "kms:ScheduleKeyDeletion", "organizations:"]

deny contains msg if {
	some node in input.nodes
	node.type == "IAMPolicy"
	some action in node.attributes.actions
	some pattern in forbidden_patterns
	startswith(action, pattern)
	msg := sprintf("forbidden permission %q on policy node %q", [action, node.id])
}

# --- required tags present on every node -------------------------------------
required_tags := ["env", "owner", "app"]

deny contains msg if {
	some node in input.nodes
	some tag in required_tags
	not node.tags[tag]
	msg := sprintf("node %q is missing required tag %q", [node.id, tag])
}

# --- resource budget (mirrors scenario constraints.max_resources) ------------
max_resources := 40

deny contains msg if {
	count(input.nodes) > max_resources
	msg := sprintf("resource count %d exceeds max %d", [count(input.nodes), max_resources])
}

# --- required critical chain must exist --------------------------------------
# The CI/CD -> DeployRole -> RuntimeRole -> sensitive bucket chain must be present.
has_assume if {
	some e in input.edges
	e.type == "assumes"
}

has_passrole if {
	some e in input.edges
	e.type == "can_pass_role"
}

has_sensitive_read if {
	some e in input.edges
	e.type == "can_read"
}

deny contains msg if {
	not has_assume
	msg := "missing required 'assumes' edge (CI/CD identity -> deploy role)"
}

deny contains msg if {
	not has_passrole
	msg := "missing required 'can_pass_role' edge (deploy role -> runtime role)"
}

deny contains msg if {
	not has_sensitive_read
	msg := "missing required 'can_read' edge (runtime role -> sensitive bucket)"
}
