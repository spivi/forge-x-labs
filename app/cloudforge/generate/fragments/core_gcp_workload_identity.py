"""core.gcp_workload_identity_federation — GCP Workload Identity Federation."""

from __future__ import annotations

from random import Random
from typing import Any

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

_TAGS = NodeTags(env="prod", owner="gcp-infra", app="data-warehouse")


def _nid(ns: str, node_id: str) -> str:
    return f"{ns}/{node_id}" if ns else node_id


def _node(
    ns: str, node_id: str, ntype: NodeType, name: str, crit: str, **attrs: str | list[str]
) -> GraphNode:
    return GraphNode(
        id=_nid(ns, node_id),
        type=ntype,
        name=name,
        tags=_TAGS,
        security=NodeSecurity(criticality=crit),
        attributes=dict(attrs),
    )


def _edge(ns: str, src: str, dst: str, etype: EdgeType, risk: str) -> GraphEdge:
    return GraphEdge(
        from_=_nid(ns, src), to=_nid(ns, dst), type=etype, security=EdgeSecurity(risk=risk)
    )


def _ek(ns: str, src: str, etype: EdgeType, dst: str) -> str:
    return f"{_nid(ns, src)}->{etype.value}->{_nid(ns, dst)}"


@register("core.gcp_workload_identity_federation")
@register("core.gcp_workload_identity")
class GcpWorkloadIdentity:
    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        return FragmentBundle(
            nodes=_nodes(ns), edges=_edges(ns), findings=_findings(ns), paths=[_critical(ns)]
        )


def _nodes(ns: str) -> list[GraphNode]:
    return [
        _node(
            ns,
            "org-cloud-enterprise",
            NodeType.GCP_ORGANIZATION,
            "org-cloud-enterprise",
            "medium",
            org_id="123456789012",
        ),
        _node(
            ns,
            "prj-analytics-prod",
            NodeType.GCP_PROJECT,
            "prj-analytics-prod",
            "medium",
            project_id="prj-analytics-prod-101",
        ),
        _node(
            ns,
            "pool-github-actions",
            NodeType.GCP_WORKLOAD_IDENTITY_POOL,
            "pool-github-actions",
            "high",
            issuer_uri="https://token.actions.githubusercontent.com",
        ),
        _node(
            ns,
            "sa-workload-deployer",
            NodeType.GCP_SERVICE_ACCOUNT,
            "sa-workload-deployer",
            "critical",
            email="sa-workload-deployer@prj-analytics-prod-101.iam.gserviceaccount.com",
        ),
        _node(
            ns,
            "bkt-enterprise-analytics",
            NodeType.GCP_STORAGE_BUCKET,
            "bkt-enterprise-analytics",
            "critical",
            bucket_name="bkt-enterprise-analytics",
        ),
        _node(
            ns,
            "enterprise-analytics",
            NodeType.DATASET,
            "enterprise-analytics",
            "critical",
            classification="restricted",
        ),
    ]


def _edges(ns: str) -> list[GraphEdge]:
    return [
        _edge(
            ns,
            "org-cloud-enterprise",
            "prj-analytics-prod",
            EdgeType.ORGANIZATIONAL_CHILD,
            "none",
        ),
        _edge(
            ns,
            "prj-analytics-prod",
            "pool-github-actions",
            EdgeType.ORGANIZATIONAL_CHILD,
            "none",
        ),
        _edge(
            ns,
            "pool-github-actions",
            "sa-workload-deployer",
            EdgeType.FEDERATES_TO,
            "critical",
        ),
        _edge(
            ns,
            "sa-workload-deployer",
            "bkt-enterprise-analytics",
            EdgeType.CAN_READ,
            "critical",
        ),
        _edge(
            ns,
            "bkt-enterprise-analytics",
            "enterprise-analytics",
            EdgeType.STORES_SENSITIVE_DATA,
            "critical",
        ),
    ]


def _findings(ns: str) -> list[ExpectedFinding]:
    return [
        ExpectedFinding(
            id=_nid(ns, "finding-gcp-wif-01"),
            severity="critical",
            family=FindingFamily.GCP_WORKLOAD_IDENTITY_FEDERATION,
            resource_ids=[
                _nid(ns, "pool-github-actions"),
                _nid(ns, "sa-workload-deployer"),
                _nid(ns, "bkt-enterprise-analytics"),
            ],
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


def _critical(ns: str) -> GroundTruthPath:
    return GroundTruthPath(
        id=_nid(ns, "path-critical-gcp-wif-01"),
        severity="critical",
        nodes=[
            _nid(ns, "pool-github-actions"),
            _nid(ns, "sa-workload-deployer"),
            _nid(ns, "bkt-enterprise-analytics"),
            _nid(ns, "enterprise-analytics"),
        ],
        edges=[
            _ek(ns, "pool-github-actions", EdgeType.FEDERATES_TO, "sa-workload-deployer"),
            _ek(ns, "sa-workload-deployer", EdgeType.CAN_READ, "bkt-enterprise-analytics"),
            _ek(
                ns,
                "bkt-enterprise-analytics",
                EdgeType.STORES_SENSITIVE_DATA,
                "enterprise-analytics",
            ),
        ],
        sink_kind=SinkKind.DATA,
        target=_nid(ns, "enterprise-analytics"),
        explanation=(
            "Unrestricted Workload Identity Pool federates into high-privilege service "
            "account accessing enterprise storage bucket"
        ),
    )
