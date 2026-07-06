# Native `opa test` unit tests for policies/scenario.rego (FXL-STRESS-6).
#
# Run: opa test policies/ -v
# Coverage: opa test policies/ --coverage --format=json
#
# Each `test_` rule builds a minimal, self-contained `input` graph (not the real
# generator fixtures — those are covered by tests/cloudforge/test_opa_policy.py,
# which runs `opa eval` over actual generated scenarios). These tests instead
# exist to pin down each `deny` rule's boundary in isolation, including cases
# the generator never produces (so the policy is proven, not just exercised).

package cloudforge_test

import data.cloudforge
import rego.v1

# --- shared minimal valid graph ------------------------------------------------
# Small, internally-consistent, family-agnostic graph that must satisfy every
# deny rule: tagged nodes, no forbidden perms, under budget, one critical edge
# reaching a stores_sensitive_data sink, no secret-shaped attributes.

_tags := {"env": "staging", "owner": "platform-team", "app": "demo"}

_valid_nodes := [
	{
		"id": "sg-web",
		"type": "SecurityGroup",
		"name": "web-sg",
		"tags": _tags,
		"security": {"criticality": "high"},
		"attributes": {"ingress_cidr": "0.0.0.0/0"},
	},
	{
		"id": "s3-data",
		"type": "S3Bucket",
		"name": "data-bucket",
		"tags": _tags,
		"security": {"criticality": "critical"},
		"attributes": {},
	},
	{
		"id": "dataset-customer",
		"type": "DataSet",
		"name": "customer-data",
		"tags": _tags,
		"security": {"criticality": "critical"},
		"attributes": {},
	},
	{
		"id": "pol-runtime",
		"type": "IAMPolicy",
		"name": "RuntimePolicy",
		"tags": _tags,
		"security": {"criticality": "high"},
		"attributes": {"actions": ["s3:GetObject", "s3:ListBucket"]},
	},
]

_valid_edges := [
	{
		"from": "sg-web",
		"to": "s3-data",
		"type": "exposed_to_internet",
		"security": {"risk": "critical"},
	},
	{
		"from": "s3-data",
		"to": "dataset-customer",
		"type": "stores_sensitive_data",
		"security": {"risk": "critical"},
	},
]

_valid_graph := {"nodes": _valid_nodes, "edges": _valid_edges}

# --- valid graph -> no deny ----------------------------------------------------

test_valid_graph_has_no_denials if {
	count(cloudforge.deny) == 0 with input as _valid_graph
}

# --- required tags --------------------------------------------------------------

test_missing_required_tag_denies if {
	bad_node := json.remove(_valid_nodes[0], ["/tags/app"])
	graph := object.union(_valid_graph, {"nodes": [bad_node, _valid_nodes[1], _valid_nodes[2], _valid_nodes[3]]})
	denials := cloudforge.deny with input as graph
	count(denials) > 0
	some msg in denials
	contains(msg, "missing required tag")
	contains(msg, "app")
}

test_all_required_tags_present_no_tag_denial if {
	denials := cloudforge.deny with input as _valid_graph
	not any_contains(denials, "missing required tag")
}

# --- forbidden permissions -------------------------------------------------------

test_forbidden_iam_delete_denies if {
	bad_policy := object.union(_valid_nodes[3], {"attributes": {"actions": ["iam:DeleteRole"]}})
	graph := object.union(_valid_graph, {"nodes": [_valid_nodes[0], _valid_nodes[1], _valid_nodes[2], bad_policy]})
	denials := cloudforge.deny with input as graph
	some msg in denials
	contains(msg, "forbidden permission")
	contains(msg, "iam:DeleteRole")
}

test_forbidden_s3_delete_bucket_denies if {
	bad_policy := object.union(_valid_nodes[3], {"attributes": {"actions": ["s3:DeleteBucket"]}})
	graph := object.union(_valid_graph, {"nodes": [_valid_nodes[0], _valid_nodes[1], _valid_nodes[2], bad_policy]})
	denials := cloudforge.deny with input as graph
	some msg in denials
	contains(msg, "forbidden permission")
}

test_forbidden_organizations_wildcard_denies if {
	bad_policy := object.union(_valid_nodes[3], {"attributes": {"actions": ["organizations:LeaveOrganization"]}})
	graph := object.union(_valid_graph, {"nodes": [_valid_nodes[0], _valid_nodes[1], _valid_nodes[2], bad_policy]})
	denials := cloudforge.deny with input as graph
	some msg in denials
	contains(msg, "forbidden permission")
}

test_allowed_broad_read_does_not_trigger_forbidden_denial if {
	denials := cloudforge.deny with input as _valid_graph
	not any_contains(denials, "forbidden permission")
}

# --- resource budget --------------------------------------------------------------

test_over_resource_budget_denies if {
	filler := [n |
		some i in numbers.range(1, 45)
		n := object.union(_valid_nodes[0], {"id": sprintf("filler-%d", [i])})
	]
	graph := object.union(_valid_graph, {"nodes": filler})
	denials := cloudforge.deny with input as graph
	some msg in denials
	contains(msg, "exceeds max")
}

test_under_resource_budget_no_budget_denial if {
	denials := cloudforge.deny with input as _valid_graph
	not any_contains(denials, "exceeds max")
}

test_exactly_at_budget_no_budget_denial if {
	filler := [n |
		some i in numbers.range(1, 40)
		n := object.union(_valid_nodes[0], {"id": sprintf("filler-%d", [i])})
	]
	graph := object.union(_valid_graph, {"nodes": filler})
	denials := cloudforge.deny with input as graph
	not any_contains(denials, "exceeds max")
}

# --- critical-path-missing / no-sensitive-sink (family-agnostic) ------------------

test_no_critical_edge_denies if {
	edges := [object.union(e, {"security": {"risk": "low"}}) | some e in _valid_edges]
	graph := object.union(_valid_graph, {"edges": edges})
	denials := cloudforge.deny with input as graph
	some msg in denials
	contains(msg, "no critical-risk edge")
}

test_no_sensitive_sink_denies if {
	edges := [e | some e in _valid_edges; e.type != "stores_sensitive_data"]
	graph := object.union(_valid_graph, {"edges": edges})
	denials := cloudforge.deny with input as graph
	some msg in denials
	contains(msg, "sensitive-data sink")
}

test_critical_edge_and_sink_present_no_path_denial if {
	denials := cloudforge.deny with input as _valid_graph
	not any_contains(denials, "critical risk path")
	not any_contains(denials, "sensitive-data sink")
}

# --- no real secrets in attributes (FXL-STRESS-6 gap fix) -------------------------

test_aws_secret_access_key_value_denies if {
	leaky := object.union(_valid_nodes[0], {"attributes": {"aws_secret_access_key": "wJalrXUtnFEMIK7MDENGbPxRfiCYEXAMPLEKEY"}})
	graph := object.union(_valid_graph, {"nodes": [leaky, _valid_nodes[1], _valid_nodes[2], _valid_nodes[3]]})
	denials := cloudforge.deny with input as graph
	some msg in denials
	contains(msg, "real-looking secret")
}

test_password_key_with_long_value_denies if {
	leaky := object.union(_valid_nodes[0], {"attributes": {"password": "SuperSecretPassw0rd123"}})
	graph := object.union(_valid_graph, {"nodes": [leaky, _valid_nodes[1], _valid_nodes[2], _valid_nodes[3]]})
	denials := cloudforge.deny with input as graph
	some msg in denials
	contains(msg, "real-looking secret")
}

test_short_password_value_does_not_deny if {
	# Below the minimum length threshold — not secret-shaped, avoids false positives
	# on short benign flags/placeholders.
	leaky := object.union(_valid_nodes[0], {"attributes": {"password": "short"}})
	graph := object.union(_valid_graph, {"nodes": [leaky, _valid_nodes[1], _valid_nodes[2], _valid_nodes[3]]})
	denials := cloudforge.deny with input as graph
	not any_contains(denials, "real-looking secret")
}

test_pem_private_key_value_denies_regardless_of_key_name if {
	leaky := object.union(_valid_nodes[0], {"attributes": {"debug_note": "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA\n-----END RSA PRIVATE KEY-----"}})
	graph := object.union(_valid_graph, {"nodes": [leaky, _valid_nodes[1], _valid_nodes[2], _valid_nodes[3]]})
	denials := cloudforge.deny with input as graph
	some msg in denials
	contains(msg, "real-looking secret")
}

test_aws_access_key_id_shape_denies_regardless_of_key_name if {
	leaky := object.union(_valid_nodes[0], {"attributes": {"note": "found key AKIAIOSFODNN7EXAMPLE in logs"}})
	graph := object.union(_valid_graph, {"nodes": [leaky, _valid_nodes[1], _valid_nodes[2], _valid_nodes[3]]})
	denials := cloudforge.deny with input as graph
	some msg in denials
	contains(msg, "real-looking secret")
}

test_secret_in_list_attribute_value_denies if {
	# attributes value can be list[string] (e.g. `actions`) — scan must flatten it too.
	leaky := object.union(_valid_nodes[3], {"attributes": {"actions": ["s3:GetObject", "AKIAIOSFODNN7EXAMPLE"]}})
	graph := object.union(_valid_graph, {"nodes": [_valid_nodes[0], _valid_nodes[1], _valid_nodes[2], leaky]})
	denials := cloudforge.deny with input as graph
	some msg in denials
	contains(msg, "real-looking secret")
}

test_ordinary_attributes_no_secret_denial if {
	denials := cloudforge.deny with input as _valid_graph
	not any_contains(denials, "real-looking secret")
}

# --- test helper ------------------------------------------------------------------

any_contains(msgs, needle) if {
	some msg in msgs
	contains(msg, needle)
}
