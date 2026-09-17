"""``core.secretsmanager_policy_overbroad``: an overbroad Secrets Manager policy.

What the attacker reaches is the secret itself (``sink_kind`` ``secret``): the
resource policy lets an external account call GetSecretValue on the production
database master credentials. The database those credentials open, and the
records it holds, are in the estate with no edge from the secret, off the
graded path.

Difficulty adds, through the composer's shape: a bucket the external account may
also read that holds nothing (``dead_end``), a lookalike secret shared with the
same external principal behind an org-scoped condition (``lookalike``), and an
application identity route to the same secret (``prefix_hops``), labeled as its
own high-severity path.
"""

from __future__ import annotations

from random import Random
from typing import Any

from app.cloudforge import constants
from app.cloudforge.generate.fragments import _aws_shape as aws
from app.cloudforge.generate.fragments._core import Kit, Piece, shape_of
from app.cloudforge.generate.fragments._vocab import LOOKALIKE_SECRETS
from app.cloudforge.generate.fragments.base import FragmentBundle, register
from app.cloudforge.models.findings import (
    ExpectedFinding,
    FindingFamily,
    GroundTruthPath,
    SinkKind,
)
from app.cloudforge.models.graph import EdgeType, GraphEdge, GraphNode, NodeTags, NodeType

_TAGS = NodeTags(env="prod", owner="secrets-management-team", app="vault-service")
_EXT = constants.EXTERNAL_DUMMY_ACCOUNT_ID
_ENTRY = "acct-external"
_SINK = "sec-db-creds"
_ACTIONS = ["secretsmanager:GetSecretValue"]


@register("core.secretsmanager_policy_overbroad")
class SecretsManagerPolicyOverbroad:
    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        kit = Kit(ns, _TAGS)
        extra = aws.extend(kit, rng, shape_of(params), _story(), _lookalike)
        return FragmentBundle(
            nodes=_nodes(kit) + extra.nodes,
            edges=_edges(kit) + extra.edges,
            findings=_findings(kit) + extra.findings,
            paths=[_critical(kit), *extra.paths],
        )


def _story() -> aws.Story:
    return aws.Story(
        entry=_ENTRY,
        resource=_SINK,
        tail=[_SINK],
        tail_edges=[],
        actions=list(_ACTIONS),
        sink_kind=SinkKind.SECRET,
        stem="secrets",
        dead_end=aws.dead_end_readable_bucket,
    )


def _lookalike(kit: Kit, rng: Random) -> Piece:
    return aws.lookalike(
        kit,
        rng,
        _ENTRY,
        EdgeType.CAN_READ,
        "sec",
        NodeType.SECRETS_MANAGER_SECRET,
        LOOKALIKE_SECRETS,
        **aws.conditioned(principal=_EXT, actions=list(_ACTIONS)),
    )


def _nodes(kit: Kit) -> list[GraphNode]:
    return [
        kit.node("acct-main", NodeType.ACCOUNT, "prod-account", "medium"),
        kit.node(_ENTRY, NodeType.ACCOUNT, "external-account", "high", account_id=_EXT),
        kit.node(
            _SINK,
            NodeType.SECRETS_MANAGER_SECRET,
            "prod-db-master-credentials",
            "critical",
            principal=_EXT,
            actions=list(_ACTIONS),
        ),
        kit.node(
            "rds-prod-primary",
            NodeType.RDS_INSTANCE,
            "prod-postgres-primary",
            "high",
            publicly_accessible="false",
        ),
        kit.node(
            "data-prod-db-records",
            NodeType.DATASET,
            "production-database-records",
            "critical",
            classification="restricted",
        ),
    ]


def _edges(kit: Kit) -> list[GraphEdge]:
    return [
        kit.edge(_ENTRY, _SINK, EdgeType.CAN_READ, "critical"),
        kit.edge(
            "rds-prod-primary", "data-prod-db-records", EdgeType.STORES_SENSITIVE_DATA, "none"
        ),
    ]


def _findings(kit: Kit) -> list[ExpectedFinding]:
    return [
        ExpectedFinding(
            id=kit.nid("finding-secretsmanager-policy-overbroad-01"),
            severity="critical",
            family=FindingFamily.SECRETSMANAGER_POLICY_OVERBROAD,
            resource_ids=[kit.nid(_SINK)],
            expected_scanner_visibility="visible",
            ground_truth=(
                "Secrets Manager secret resource policy permits external account "
                "to read database credentials"
            ),
            remediation="Remove external account principal from Secrets Manager resource policy",
        ),
    ]


def _critical(kit: Kit) -> GroundTruthPath:
    return GroundTruthPath(
        id=kit.nid("path-critical-secrets-01"),
        severity="critical",
        nodes=[kit.nid(_ENTRY), kit.nid(_SINK)],
        edges=[kit.ek(_ENTRY, EdgeType.CAN_READ, _SINK)],
        sink_kind=SinkKind.SECRET,
        target=kit.nid(_SINK),
        explanation=(
            "The resource policy on prod-db-master-credentials grants "
            "secretsmanager:GetSecretValue to an untrusted external account, which "
            "reads the master credentials directly"
        ),
    )
