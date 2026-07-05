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

# --- a coherent critical risk path must exist (family-agnostic) --------------
# FXL-54: this used to hardcode the ci_cd_iam_chain edge types (`assumes`,
# `can_pass_role`, `can_read`) as a *universal* requirement, wrongly denying every
# other family (e.g. `public_data_exposure`, whose critical path is
# `exposed_to_internet -> stores_sensitive_data`, no IAM role chain).
#
# The Python graph-risk engine owns per-family ground-truth path validation. This
# rego is only a coarse sanity gate, so it asserts — without naming any one
# family's edges — that the graph contains a critical risk terminating in a
# sensitive-data sink:
#   (a) at least one edge whose `security.risk == "critical"`, AND
#   (b) at least one `stores_sensitive_data` edge (the sensitive-data sink).
# Both shipped families satisfy this (ci_cd: `can_pass_role`/`can_read` are risk
# critical + `stores_sensitive_data`; pde: `exposed_to_internet` is risk critical +
# `stores_sensitive_data`), while a graph with no critical-risk edge or no sink is
# still denied.
has_critical_edge if {
	some e in input.edges
	e.security.risk == "critical"
}

has_sensitive_sink if {
	some e in input.edges
	e.type == "stores_sensitive_data"
}

deny contains msg if {
	not has_critical_edge
	msg := "no critical-risk edge — scenario has no coherent critical risk path"
}

deny contains msg if {
	not has_sensitive_sink
	msg := "no 'stores_sensitive_data' edge — critical risk has no sensitive-data sink"
}
