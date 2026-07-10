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

# --- resource budget (coarse ceiling across all deployable scale tiers) -------
# OPA evaluates over graph.json alone and cannot read the scenario's per-scenario
# `constraints.max_resources` / `scale_profile`. So this is a coarse upper bound:
# the node count of the largest *deployable* scale profile (`large` = 500 nodes;
# `xlarge` is graph-only and not terraform/OPA-gated). The tight per-scenario
# budget (`max(constraints.max_resources, scale_profile.max_nodes)`) is enforced
# by the Python graph-risk engine; this rego only catches a runaway graph.
max_resources := 500

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

# --- no real secrets in node attributes (FXL-STRESS-6, mirrors constraints.no_real_secrets) --
# Coarse, family-agnostic scan over every node's `attributes` (the only freeform payload
# on a graph node — IAM actions, CIDRs, bucket names, arns, ...). `attributes` is a plain
# `{key: value}` map (value is `string | list[string]`), never an inline `key=value`
# string, so a leaked secret shows up either as (a) a sensitively-named key holding a
# long value, or (b) a self-describing value pattern (PEM header, AWS access-key-id
# shape) regardless of key name. Mirrors `learn/_safety.py`'s conservative patterns. No
# node type or edge type is named, so this applies uniformly to any family.
_sensitive_key_pattern := `(?i)^(aws_secret_access_key|secret|password|passwd|private_key|api[_-]?key)$`

# self-describing secret *values*, independent of the attribute key name.
_secret_value_pattern := `-----BEGIN [A-Z ]*PRIVATE KEY-----|(?i)\bAKIA[0-9A-Z]{16}\b`

_min_secret_len := 12

_looks_like_secret(_, value) if {
	regex.match(_secret_value_pattern, value)
}

_looks_like_secret(key, value) if {
	regex.match(_sensitive_key_pattern, key)
	count(value) >= _min_secret_len
}

# attribute values are `string | list[string]` — flatten both shapes into (key, value) pairs.
_attribute_pairs(node) := {[key, value] |
	some key, value in node.attributes
	is_string(value)
} | {[key, value] |
	some key, list in node.attributes
	is_array(list)
	some value in list
	is_string(value)
}

deny contains msg if {
	some node in input.nodes
	some pair in _attribute_pairs(node)
	_looks_like_secret(pair[0], pair[1])
	msg := sprintf("node %q attributes contain a real-looking secret (constraints.no_real_secrets)", [node.id])
}
