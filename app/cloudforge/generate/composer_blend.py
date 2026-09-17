"""Blend the path's tags and benign configuration into its padding.

Every core fragment stamps one fixed tag set on all its nodes (``env=prod``,
``owner=azure-platform``, ...) and gives the path nodes their own configuration
(``identity_type=SystemAssigned``, ``purge_protection=false``). Pool fragments
draw their own. So a student who filters the estate on ``env: prod``, or sorts
the key vaults by ``purge_protection``, reads the path off the result without
looking at an edge.

After assembly the composer therefore copies each path node's tag values and
benign attribute values onto seeded off-path nodes of the same type until at
least two of them carry the value (one when the type has fewer than three
instances, capped by how many peers exist; for tags, any off-path node when the
type has no peers at all). Two groups of attributes are never copied:

- ``RISK_ATTRIBUTES`` are the modeled misconfiguration itself. Copying
  ``imds_version=v1`` or an IAM grant onto padding would make the padding
  genuinely risky, and the student is supposed to be able to find the risk.
- ``IDENTIFIER_ATTRIBUTES`` are unique per resource by nature (an email, an
  ARN, a storage account name); a copy would be a lie about a different resource.

Together they are the allowlist of attributes that may legitimately exist only
on a path node. ``tests/cloudforge/lab/test_path_tells.py`` prints it and holds
it to this module, so a new path attribute must be classified before it ships.
"""

from __future__ import annotations

from collections import Counter
from random import Random

from app.cloudforge.models.findings import GroundTruthPath
from app.cloudforge.models.graph import GraphNode

RISK_ATTRIBUTES: frozenset[str] = frozenset(
    {
        "acl",
        "actions",
        "auth_type",
        "encrypted",
        "imds_version",
        "logging",
        "principal",
        "public",
        "public_access",
        "publicly_accessible",
        "trusted_principal",
    }
)

IDENTIFIER_ATTRIBUTES: frozenset[str] = frozenset(
    {
        "account_id",
        "annotations",
        "bucket_name",
        "email",
        "principal_id",
        "role_arn",
        "service_account",
        "storage_account",
    }
)

EXEMPT_ATTRIBUTES: frozenset[str] = RISK_ATTRIBUTES | IDENTIFIER_ATTRIBUTES
TAG_KEYS: tuple[str, ...] = ("env", "owner", "app")
# A type with this many instances must have two peers sharing each path value.
CROWD = 3
PEERS_WANTED = 2


def blend_into_padding(nodes: list[GraphNode], paths: list[GroundTruthPath], rng: Random) -> None:
    """Copy path tag values and benign attribute values onto off-path peers in place."""
    on_path = {nid for path in paths for nid in path.nodes}
    path_nodes = [n for n in nodes if n.id in on_path]
    off_path = [n for n in nodes if n.id not in on_path]
    counts = Counter(n.type for n in nodes)
    for node in path_nodes:
        peers = [n for n in off_path if n.type is node.type]
        wanted = PEERS_WANTED if counts[node.type] >= CROWD else 1
        for key in TAG_KEYS:
            pool = peers or off_path
            _ensure_tag(rng, pool, min(wanted, len(pool)), key, getattr(node.tags, key))
        if not peers:
            continue
        for key, value in node.attributes.items():
            if key not in EXEMPT_ATTRIBUTES:
                _ensure_attribute(rng, peers, min(wanted, len(peers)), key, value)


def _ensure_tag(rng: Random, pool: list[GraphNode], wanted: int, key: str, value: str) -> None:
    have = [n for n in pool if getattr(n.tags, key) == value]
    lacking = [n for n in pool if getattr(n.tags, key) != value]
    for node in _draw(rng, lacking, wanted - len(have)):
        # Fragments share one NodeTags object among their nodes; copy before changing.
        node.tags = node.tags.model_copy(update={key: value})


def _ensure_attribute(
    rng: Random, peers: list[GraphNode], wanted: int, key: str, value: str | list[str]
) -> None:
    have = [n for n in peers if n.attributes.get(key) == value]
    lacking = [n for n in peers if n.attributes.get(key) != value]
    for node in _draw(rng, lacking, wanted - len(have)):
        node.attributes[key] = list(value) if isinstance(value, list) else value


def _draw(rng: Random, candidates: list[GraphNode], short: int) -> list[GraphNode]:
    if short <= 0 or not candidates:
        return []
    return rng.sample(candidates, min(short, len(candidates)))
