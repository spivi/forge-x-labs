"""Resource-address <-> graph-node matching for the scanner scorer.

Checkov emits resource-level findings keyed by a Terraform resource ADDRESS
(``aws_iam_role.role_deploy``); the graph's expected findings are keyed by GRAPH
NODE ids (``role-deploy``). This module inverts the emitter's ``resource_name``
mapping to link one back to the other, and counts "unexpected" (unmatched)
findings without ever hiding them — a failed-check that cannot be resolved to any
node is still counted, keyed by its raw resource address.
"""

from __future__ import annotations

from app.cloudforge.models.graph import ScenarioGraph
from app.cloudforge.pipeline.identifiers import resource_name


def unexpected_count(
    graph: ScenarioGraph, failed_resources: list[str], matched_nodes: set[str]
) -> int:
    """Distinct failed-check targets that touch no expected-finding node.

    Deduped by graph node when the resource resolves to one (so a node emitting two
    Terraform resources — e.g. a bucket + its bucket policy sharing one label — counts
    once, consistent with the node-set matched/missed counts); an unresolvable resource
    (mapping to no node at all) is keyed by its address, as it has no node to dedup by.
    """
    unexpected: set[str] = set()
    for resource in failed_resources:
        node_id = resolve_node_id(graph, resource)
        if node_id is None:
            unexpected.add(resource)
        elif node_id not in matched_nodes:
            unexpected.add(node_id)
    return len(unexpected)


def resource_to_node_ids(graph: ScenarioGraph, failed_resources: list[str]) -> set[str]:
    resolved: set[str] = set()
    for resource in failed_resources:
        node_id = resolve_node_id(graph, resource)
        if node_id is not None:
            resolved.add(node_id)
    return resolved


def resolve_node_id(graph: ScenarioGraph, resource: str) -> str | None:
    """Invert the emitter mapping: ``aws_<type>.<label>`` -> graph ``node.id``.

    Strip the ``aws_<type>.`` prefix to the bare Terraform label, then match it against
    ``resource_name(node)`` (the exact transform the emitter applied).
    """
    label = resource.rsplit(".", 1)[-1]
    for node in graph.nodes:
        if resource_name(node) == label:
            return node.id
    return None
