"""core.gcp_workload_identity_federation: an unrestricted pool walks to GCS.

Story: pool-github-actions has no attribute condition, so any GitHub workflow
can exchange its token for sa-workload-deployer. On the direct chain that
account reads the enterprise analytics bucket; with ``extra_hops`` it holds
``roles/iam.serviceAccountTokenCreator`` on a chain of service accounts and
impersonates each in turn, and the last one reads the bucket. With
``dead_end`` the pool also federates to a second account whose only grant
reaches a bucket of build output.
"""

from __future__ import annotations

from random import Random
from typing import Any

from app.cloudforge.generate.fragments._core import Kit, Piece, draw_hops, hop_lines, shape_of
from app.cloudforge.generate.fragments._vocab import GCP_DEAD_ENDS, GCP_HOP_ACCOUNTS
from app.cloudforge.generate.fragments.base import FragmentBundle, register
from app.cloudforge.models.findings import (
    ExpectedFinding,
    FindingFamily,
    GroundTruthPath,
    SinkKind,
)
from app.cloudforge.models.graph import EdgeType, GraphEdge, GraphNode, NodeTags, NodeType

_TAGS = NodeTags(env="prod", owner="gcp-infra", app="data-warehouse")
_PROJECT_ID = "prj-analytics-prod-101"
_ENTRY = "pool-github-actions"
_HEAD = "sa-workload-deployer"
_BUCKET = "bkt-enterprise-analytics"
_SINK = "enterprise-analytics"


def _email(name: str) -> str:
    return f"{name}@{_PROJECT_ID}.iam.gserviceaccount.com"


@register("core.gcp_workload_identity_federation")
@register("core.gcp_workload_identity")
class GcpWorkloadIdentity:
    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        kit = Kit(ns, _TAGS)
        shape = shape_of(params)
        hops = draw_hops(
            kit, rng, shape.extra_hops, GCP_HOP_ACCOUNTS, "sa", NodeType.GCP_SERVICE_ACCOUNT
        )
        for node in hops.nodes:
            node.attributes["email"] = _email(node.name)
        chain = [_HEAD, *hops.ids]
        nodes = _nodes(kit) + hops.nodes
        edges = _edges(kit, chain)
        if shape.dead_end:
            branch = _dead_end(kit, rng)
            nodes, edges = nodes + branch.nodes, edges + branch.edges
        names = [_HEAD, *hops.names]
        return FragmentBundle(
            nodes=nodes,
            edges=edges,
            findings=_findings(kit, chain[-1]),
            paths=[_critical(kit, chain, names)],
        )


def _nodes(kit: Kit) -> list[GraphNode]:
    return [
        kit.node(
            "org-cloud-enterprise",
            NodeType.GCP_ORGANIZATION,
            "org-cloud-enterprise",
            "medium",
            org_id="123456789012",
        ),
        kit.node(
            "prj-analytics-prod",
            NodeType.GCP_PROJECT,
            "prj-analytics-prod",
            "medium",
            project_id=_PROJECT_ID,
        ),
        kit.node(
            _ENTRY,
            NodeType.GCP_WORKLOAD_IDENTITY_POOL,
            _ENTRY,
            "high",
            issuer_uri="https://token.actions.githubusercontent.com",
        ),
        kit.node(_HEAD, NodeType.GCP_SERVICE_ACCOUNT, _HEAD, "critical", email=_email(_HEAD)),
        kit.node(_BUCKET, NodeType.GCP_STORAGE_BUCKET, _BUCKET, "critical", bucket_name=_BUCKET),
        kit.node(_SINK, NodeType.DATASET, _SINK, "critical", classification="restricted"),
    ]


def _edges(kit: Kit, chain: list[str]) -> list[GraphEdge]:
    reader = chain[-1]
    return [
        kit.edge(
            "org-cloud-enterprise", "prj-analytics-prod", EdgeType.ORGANIZATIONAL_CHILD, "none"
        ),
        kit.edge("prj-analytics-prod", _ENTRY, EdgeType.ORGANIZATIONAL_CHILD, "none"),
        kit.edge(_ENTRY, _HEAD, EdgeType.FEDERATES_TO, "critical"),
        *kit.chain(chain, EdgeType.IMPERSONATES, "critical"),
        kit.edge(reader, _BUCKET, EdgeType.CAN_READ, "critical"),
        kit.edge(_BUCKET, _SINK, EdgeType.STORES_SENSITIVE_DATA, "critical"),
    ]


def _dead_end(kit: Kit, rng: Random) -> Piece:
    """A second account the pool federates to, granted only a build bucket."""
    sa_name, bucket_name = rng.choice(GCP_DEAD_ENDS)
    return Piece(
        nodes=[
            kit.node(
                sa_name,
                NodeType.GCP_SERVICE_ACCOUNT,
                sa_name,
                "low",
                email=_email(sa_name),
                role="roles/storage.objectCreator",
            ),
            kit.node(
                bucket_name,
                NodeType.GCP_STORAGE_BUCKET,
                bucket_name,
                "low",
                storage_class="STANDARD",
            ),
        ],
        edges=[
            kit.edge(_ENTRY, sa_name, EdgeType.FEDERATES_TO, "low"),
            kit.edge(sa_name, bucket_name, EdgeType.CAN_READ, "low"),
        ],
    )


def _findings(kit: Kit, reader: str) -> list[ExpectedFinding]:
    resources = [kit.nid(_ENTRY), kit.nid(_HEAD), kit.nid(reader), kit.nid(_BUCKET)]
    return [
        ExpectedFinding(
            id=kit.nid("finding-gcp-wif-01"),
            severity="critical",
            family=FindingFamily.GCP_WORKLOAD_IDENTITY_FEDERATION,
            resource_ids=list(dict.fromkeys(resources)),
            expected_scanner_visibility="visible",
            ground_truth=(
                "Workload Identity Pool lacks strict attribute condition enabling "
                "unauthorized token exchange"
            ),
            remediation=(
                "Configure attribute_condition on workload identity pool provider "
                "to bind repository and ref"
            ),
        ),
    ]


def _critical(kit: Kit, chain: list[str], names: list[str]) -> GroundTruthPath:
    reader = chain[-1]
    return GroundTruthPath(
        id=kit.nid("path-critical-gcp-wif-01"),
        severity="critical",
        nodes=[kit.nid(n) for n in [_ENTRY, *chain, _BUCKET, _SINK]],
        edges=[
            kit.ek(_ENTRY, EdgeType.FEDERATES_TO, _HEAD),
            *kit.chain_keys(chain, EdgeType.IMPERSONATES),
            kit.ek(reader, EdgeType.CAN_READ, _BUCKET),
            kit.ek(_BUCKET, EdgeType.STORES_SENSITIVE_DATA, _SINK),
        ],
        sink_kind=SinkKind.DATA,
        target=kit.nid(_SINK),
        explanation=(
            f"Unrestricted Workload Identity Pool federates into {_HEAD}"
            + (
                f"; {hop_lines(names, 'holds iam.serviceAccountTokenCreator on and impersonates')}"
                if len(names) > 1
                else ""
            )
            + f"; {names[-1]} reads the enterprise storage bucket"
        ),
    )
