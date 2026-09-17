"""Pure, seeded transforms used by ``MutationGenerator``.

Every function here is deterministic given the explicit ``random.Random`` instance
it receives — no global RNG, no wall-clock, no PID. Mutations are cosmetic
(display ``name``/``tags``) or benign-additive (an unused subnet); node ``id``s and
every ground-truth-relevant edge are left untouched so ground truth still resolves.
"""

from __future__ import annotations

from random import Random

from app.cloudforge.models.graph import (
    EdgeSecurity,
    EdgeType,
    GraphEdge,
    GraphNode,
    NodeSecurity,
    NodeTags,
    NodeType,
    ScenarioGraph,
)

# Fixed benign vocabularies — tag values are drawn from these (never free text) so a
# mutation can never smuggle a secret (honours the ``no_real_secrets`` constraint).
_ENV_VALUES = ("staging", "stage", "preprod", "test", "sandbox")
_OWNER_VALUES = ("platform-team", "infra-team", "sre-team", "devops-crew", "cloud-eng")
_APP_VALUES = ("analytics-exporter", "data-exporter", "report-pipeline", "etl-runner")

# Cosmetic rename affixes for display names (never applied to ids).
_NAME_SUFFIXES = ("", "-v2", "-b", "-alt", "-r1", "-x")
_NAME_PREFIXES = ("", "svc-", "res-", "app-", "env-")

# Benign extra subnet: a spare, unused address block with no edges into the chain.
# ``EXTRA_SUBNET_ID`` is the canonical id of the one benign-additive node the mutation
# engine may inject; it is public so the variation harness can canonicalize it out of a
# graph-shape signature (a cosmetic mutation must not change the shape). Single source of
# truth — do not duplicate the literal elsewhere.
EXTRA_SUBNET_ID = "subnet-benign-extra"
_EXTRA_SUBNET_CIDRS = ("10.0.9.0/24", "10.0.10.0/24", "10.0.11.0/24", "10.0.12.0/24")


def jitter_tags(tags: NodeTags, rng: Random) -> NodeTags:
    """Return tags with each value re-drawn from its benign vocabulary."""
    return NodeTags(
        env=rng.choice(_ENV_VALUES),
        owner=rng.choice(_OWNER_VALUES),
        app=rng.choice(_APP_VALUES),
    )


def rename(name: str, rng: Random) -> str:
    """Return a cosmetically renamed display name (deterministic per rng draw)."""
    prefix = rng.choice(_NAME_PREFIXES)
    suffix = rng.choice(_NAME_SUFFIXES)
    return f"{prefix}{name}{suffix}"


def mutate_node(node: GraphNode, rng: Random) -> GraphNode:
    """Return a copy of ``node`` with a renamed display name and jittered tags.

    The ``id``, ``type``, ``security`` and ``attributes`` are preserved verbatim so
    ground-truth paths, findings, and the risk engine still resolve.
    """
    return node.model_copy(
        update={"name": rename(node.name, rng), "tags": jitter_tags(node.tags, rng)}
    )


def make_benign_subnet(rng: Random) -> GraphNode:
    """Build a benign, unused extra subnet node (no actions, low criticality)."""
    return GraphNode(
        id=EXTRA_SUBNET_ID,
        type=NodeType.SUBNET,
        name=rename("spare-subnet", rng),
        tags=jitter_tags(
            NodeTags(env="staging", owner="platform-team", app="analytics-exporter"), rng
        ),
        security=NodeSecurity(criticality="low"),
        attributes={"cidr": rng.choice(_EXTRA_SUBNET_CIDRS)},
    )


def make_benign_edge(subnet_id: str, vpc_id: str) -> GraphEdge:
    """Build a benign ``subnet -> vpc`` membership edge with no risk."""
    return GraphEdge(
        from_=subnet_id,
        to=vpc_id,
        type=EdgeType.BELONGS_TO_APP,
        security=EdgeSecurity(risk="none"),
    )


def find_vpc_id(graph: ScenarioGraph) -> str | None:
    """Return the id of the first VPC node, or None if the graph has none."""
    return next((n.id for n in graph.nodes if n.type is NodeType.VPC), None)
