"""The AWS pieces difficulty adds to a core path: dead ends, identity routes and
compensating-control lookalikes. Shared by the AWS core fragments; the shape that
asks for them is drawn by the composer (see ``_core``).

- A dead end hangs off the entry node with benign edges and leads nowhere
  sensitive: a second role the entry can assume, a function it can invoke, a
  public-looking bucket a policy locks down, or a bucket it may read that holds
  nothing labeled.
- An identity route is the second way a resource-shaped family's exposed
  resource is reached: an application role with an overbroad grant, optionally a
  CI identity in front of it. It is a real, lesser risk and is labeled as its own
  high-severity path with an ``iam_excessive_privilege`` finding.
- A lookalike is a second resource of the exposed type carrying the same risk
  attributes plus a control that makes them inert (an org-scoped policy condition,
  a private security group, encryption). The entry reaches it at low risk, so it
  is also a branch that goes nowhere.

``Story`` describes a resource-shaped family in the terms these pieces need and
``extend`` builds every piece the shape asks for in one call.
"""

from __future__ import annotations

from collections.abc import Callable
from random import Random
from typing import NamedTuple

from app.cloudforge.generate.fragments._core import Kit, Piece, Shape, slug
from app.cloudforge.generate.fragments._vocab import (
    AWS_DEAD_END_BUCKETS,
    AWS_DEAD_END_FUNCTIONS,
    AWS_DEAD_END_ROLES,
    AWS_PREFIX_IDENTITIES,
    AWS_READABLE_BUCKETS,
    LOOKALIKE_CONDITION,
)
from app.cloudforge.models.findings import (
    ExpectedFinding,
    FindingFamily,
    GroundTruthPath,
    SinkKind,
)
from app.cloudforge.models.graph import EdgeType, GraphEdge, GraphNode, NodeType

CONDITION_KEY, CONDITION_VALUE = LOOKALIKE_CONDITION
COMPENSATED = "true"
# A route of this many hops puts a CI identity in front of the application role.
_WITH_CI = 2

DeadEnd = Callable[[Kit, Random, str], Piece]
Lookalike = Callable[[Kit, Random], Piece]


def dead_end_role(kit: Kit, rng: Random, entry: str) -> Piece:
    """A second role ``entry`` can assume whose only grant reaches nothing sensitive."""
    role_name, policy_name, actions = rng.choice(AWS_DEAD_END_ROLES)
    role_id, policy_id = slug("role", role_name), slug("pol", policy_name)
    return Piece(
        nodes=[
            kit.node(role_id, NodeType.IAM_ROLE, role_name, "medium"),
            kit.node(policy_id, NodeType.IAM_POLICY, policy_name, "low", actions=list(actions)),
        ],
        edges=[
            kit.edge(entry, role_id, EdgeType.ASSUMES, "low"),
            kit.edge(role_id, policy_id, EdgeType.ATTACHED_POLICY, "low"),
        ],
    )


def dead_end_function(kit: Kit, rng: Random, entry: str) -> Piece:
    """A function ``entry`` can invoke, running as a role that reads nothing."""
    function_name, role_name = rng.choice(AWS_DEAD_END_FUNCTIONS)
    function_id, role_id = slug("lambda", function_name), slug("role", role_name)
    return Piece(
        nodes=[
            kit.node(
                function_id, NodeType.LAMBDA_FUNCTION, function_name, "medium", auth_type="AWS_IAM"
            ),
            kit.node(role_id, NodeType.IAM_ROLE, role_name, "medium"),
        ],
        edges=[
            kit.edge(entry, function_id, EdgeType.CAN_INVOKE, "low"),
            kit.edge(function_id, role_id, EdgeType.ASSUMES, "low"),
        ],
    )


def dead_end_bucket(kit: Kit, rng: Random, entry: str) -> Piece:
    """A public-looking bucket ``entry`` exposes that a bucket policy locks down."""
    stem, bucket_name = rng.choice(AWS_DEAD_END_BUCKETS)
    bucket_id = f"s3-{stem}"
    node = kit.node(
        bucket_id,
        NodeType.S3_BUCKET,
        bucket_name,
        "low",
        public_access="enabled",
        compensating_control=COMPENSATED,
    )
    return Piece(
        nodes=[node], edges=[kit.edge(entry, bucket_id, EdgeType.EXPOSED_TO_INTERNET, "low")]
    )


def dead_end_readable_bucket(kit: Kit, rng: Random, entry: str) -> Piece:
    """A bucket ``entry`` may read that holds nothing labeled."""
    stem, bucket_name = rng.choice(AWS_READABLE_BUCKETS)
    bucket_id = f"s3-{stem}"
    node = kit.node(bucket_id, NodeType.S3_BUCKET, bucket_name, "low")
    return Piece(nodes=[node], edges=[kit.edge(entry, bucket_id, EdgeType.CAN_READ, "low")])


def lookalike(
    kit: Kit,
    rng: Random,
    entry: str,
    etype: EdgeType,
    prefix: str,
    ntype: NodeType,
    names: tuple[str, ...],
    **attrs: str | list[str],
) -> Piece:
    """A second resource of the exposed type the entry reaches at low risk,
    carrying ``attrs`` (the exposed one's risk attributes) plus the control. Its
    id is the slug of the name it draws, like every other id in the estate."""
    name = rng.choice(names)
    node_id = slug(prefix, name)
    node = kit.node(node_id, ntype, name, "medium", compensating_control=COMPENSATED, **attrs)
    return Piece(nodes=[node], edges=[kit.edge(entry, node_id, etype, "low")])


def conditioned(**attrs: str | list[str]) -> dict[str, str | list[str]]:
    """``attrs`` plus the org-scoped policy condition that makes them inert."""
    return {**attrs, "condition_key": CONDITION_KEY, "condition_value": CONDITION_VALUE}


class Story(NamedTuple):
    """A resource-shaped family in the terms the shape pieces need."""

    entry: str
    resource: str
    # The resource and whatever the primary path walks after it, with the edge
    # keys of that walk, so the identity route ends at the same sink.
    tail: list[str]
    tail_edges: list[str]
    # The overbroad grant the application role on the identity route holds.
    actions: list[str]
    sink_kind: SinkKind
    # Id stem for the route's finding and path ids.
    stem: str
    dead_end: DeadEnd


class Extension(NamedTuple):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    findings: list[ExpectedFinding]
    paths: list[GroundTruthPath]


def extend(kit: Kit, rng: Random, shape: Shape, story: Story, twin: Lookalike) -> Extension:
    """Every piece ``shape`` asks for: the dead end, the lookalike, the identity route."""
    out = Extension(nodes=[], edges=[], findings=[], paths=[])
    if shape.dead_end:
        piece = story.dead_end(kit, rng, story.entry)
        out.nodes.extend(piece.nodes)
        out.edges.extend(piece.edges)
    if shape.lookalike:
        piece = twin(kit, rng)
        out.nodes.extend(piece.nodes)
        out.edges.extend(piece.edges)
    if shape.prefix_hops > 0:
        _add_identity_route(kit, rng, shape.prefix_hops, story, out)
    return out


def _add_identity_route(kit: Kit, rng: Random, hops: int, story: Story, out: Extension) -> None:
    """``hops`` identity nodes (1: an application role; 2: a CI identity that
    assumes it) that reach the exposed resource through an overbroad grant, then
    follow the story's tail to the same sink; labeled as a high-severity path."""
    ci_name, role_name, policy_name = rng.choice(AWS_PREFIX_IDENTITIES)
    role_id, policy_id = slug("role", role_name), slug("pol", policy_name)
    out.nodes.append(kit.node(role_id, NodeType.IAM_ROLE, role_name, "high"))
    out.nodes.append(
        kit.node(policy_id, NodeType.IAM_POLICY, policy_name, "high", actions=story.actions)
    )
    out.edges.append(kit.edge(role_id, policy_id, EdgeType.ATTACHED_POLICY, "high"))
    out.edges.append(kit.edge(role_id, story.resource, EdgeType.CAN_READ, "high"))
    chain, names = [role_id], [role_name]
    if hops >= _WITH_CI:
        ci_id = slug("cicd", ci_name)
        out.nodes.append(kit.node(ci_id, NodeType.CICD_IDENTITY, ci_name, "high"))
        out.edges.append(kit.edge(ci_id, role_id, EdgeType.ASSUMES, "high"))
        chain.insert(0, ci_id)
        names.insert(0, ci_name)
    out.findings.append(
        ExpectedFinding(
            id=kit.nid(f"find-{story.stem}-route-01"),
            severity="high",
            family=FindingFamily.IAM_EXCESSIVE_PRIVILEGE,
            resource_ids=[kit.nid(role_id), kit.nid(policy_id)],
            expected_scanner_visibility="visible",
            ground_truth=(
                f"{role_name} holds a broader grant than its job needs on {story.resource}"
            ),
            remediation="Scope the policy to the exact resource and actions the service uses.",
        )
    )
    out.paths.append(
        GroundTruthPath(
            id=kit.nid(f"path-high-{story.stem}-route-01"),
            severity="high",
            nodes=[kit.nid(n) for n in [*chain, *story.tail]],
            edges=[
                *kit.chain_keys(chain, EdgeType.ASSUMES),
                kit.ek(role_id, EdgeType.CAN_READ, story.resource),
                *story.tail_edges,
            ],
            sink_kind=story.sink_kind,
            target=kit.nid(story.tail[-1]),
            explanation=(
                f"{' assumes '.join(names)}; {role_name} holds {', '.join(story.actions)} "
                f"and reaches {story.resource} the same way the public route does"
            ),
        )
    )
