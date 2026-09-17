"""``core.secretsmanager_policy_overbroad``: an overbroad Secrets Manager policy.

What the attacker reaches is the secret itself (``sink_kind`` ``secret``): the
resource policy lets an external account call GetSecretValue on the production
database master credentials. The database those credentials open, and the
records it holds, are in the estate with no edge from the secret, off the
graded path.
"""

from __future__ import annotations

from random import Random
from typing import Any

from app.cloudforge import constants
from app.cloudforge.generate.fragments.base import FragmentBundle, register
from app.cloudforge.models.findings import (
    ExpectedFinding,
    FindingFamily,
    GroundTruthPath,
    SinkKind,
)
from app.cloudforge.models.graph import (
    EdgeSecurity,
    EdgeType,
    GraphEdge,
    GraphNode,
    NodeSecurity,
    NodeTags,
    NodeType,
)

_TAGS = NodeTags(env="prod", owner="secrets-management-team", app="vault-service")


def _nid(ns: str, node_id: str) -> str:
    return f"{ns}/{node_id}" if ns else node_id


def _node(
    ns: str, node_id: str, node_type: NodeType, name: str, crit: str, **attrs: str | list[str]
) -> GraphNode:
    return GraphNode(
        id=_nid(ns, node_id),
        type=node_type,
        name=name,
        tags=_TAGS,
        security=NodeSecurity(criticality=crit),
        attributes=dict(attrs),
    )


def _edge(ns: str, src: str, dst: str, edge_type: EdgeType, risk: str) -> GraphEdge:
    return GraphEdge(
        from_=_nid(ns, src),
        to=_nid(ns, dst),
        type=edge_type,
        security=EdgeSecurity(risk=risk),
    )


@register("core.secretsmanager_policy_overbroad")
class SecretsManagerPolicyOverbroad:
    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        return FragmentBundle(
            nodes=_nodes(ns),
            edges=_edges(ns),
            findings=_findings(ns),
            paths=[_critical(ns)],
        )


def _nodes(ns: str) -> list[GraphNode]:
    return [
        _node(ns, "acct-main", NodeType.ACCOUNT, "prod-account", "medium"),
        _node(
            ns,
            "acct-external",
            NodeType.ACCOUNT,
            "external-account",
            "high",
            account_id=constants.EXTERNAL_DUMMY_ACCOUNT_ID,
        ),
        _node(
            ns,
            "sec-db-creds",
            NodeType.SECRETS_MANAGER_SECRET,
            "prod-db-master-credentials",
            "critical",
            principal=constants.EXTERNAL_DUMMY_ACCOUNT_ID,
            actions=["secretsmanager:GetSecretValue"],
        ),
        _node(
            ns,
            "rds-prod-primary",
            NodeType.RDS_INSTANCE,
            "prod-postgres-primary",
            "high",
            publicly_accessible="false",
        ),
        _node(
            ns,
            "data-prod-db-records",
            NodeType.DATASET,
            "production-database-records",
            "critical",
            classification="restricted",
        ),
    ]


def _edges(ns: str) -> list[GraphEdge]:
    return [
        _edge(ns, "acct-external", "sec-db-creds", EdgeType.CAN_READ, "critical"),
        _edge(
            ns,
            "rds-prod-primary",
            "data-prod-db-records",
            EdgeType.STORES_SENSITIVE_DATA,
            "none",
        ),
    ]


def _findings(ns: str) -> list[ExpectedFinding]:
    return [
        ExpectedFinding(
            id=_nid(ns, "finding-secretsmanager-policy-overbroad-01"),
            severity="critical",
            family=FindingFamily.SECRETSMANAGER_POLICY_OVERBROAD,
            resource_ids=[_nid(ns, "sec-db-creds")],
            expected_scanner_visibility="visible",
            ground_truth=(
                "Secrets Manager secret resource policy permits external account "
                "to read database credentials"
            ),
            remediation="Remove external account principal from Secrets Manager resource policy",
        ),
    ]


def _ek(ns: str, src: str, edge_type: EdgeType, dst: str) -> str:
    return f"{_nid(ns, src)}->{edge_type.value}->{_nid(ns, dst)}"


def _critical(ns: str) -> GroundTruthPath:
    return GroundTruthPath(
        id=_nid(ns, "path-critical-secrets-01"),
        severity="critical",
        nodes=[_nid(ns, "acct-external"), _nid(ns, "sec-db-creds")],
        edges=[_ek(ns, "acct-external", EdgeType.CAN_READ, "sec-db-creds")],
        sink_kind=SinkKind.SECRET,
        target=_nid(ns, "sec-db-creds"),
        explanation=(
            "The resource policy on prod-db-master-credentials grants "
            "secretsmanager:GetSecretValue to an untrusted external account, which "
            "reads the master credentials directly"
        ),
    )
