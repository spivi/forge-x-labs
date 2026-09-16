"""core.k8s_pod_irsa_exfil — K8s pod IRSA token exfiltration to S3."""

from __future__ import annotations

from random import Random
from typing import Any

from app.cloudforge.generate.fragments.base import FragmentBundle, register
from app.cloudforge.models.findings import ExpectedFinding, FindingFamily, GroundTruthPath
from app.cloudforge.models.graph import (
    EdgeSecurity,
    EdgeType,
    GraphEdge,
    GraphNode,
    NodeSecurity,
    NodeTags,
    NodeType,
)

_TAGS = NodeTags(env="prod", owner="platform-k8s", app="banking-backend")
_ROLE_ARN = "arn:aws:iam::123456789012:role/EksWorkloadRole"
_OIDC = "https://oidc.eks.us-east-1.amazonaws.com/id/EXAMPLED3B761B01042F"


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


@register("core.k8s_pod_irsa_exfil")
@register("core.k8s_irsa")
class K8sPodIrsaExfil:
    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        return FragmentBundle(
            nodes=_nodes(ns), edges=_edges(ns), findings=_findings(ns), paths=[_critical(ns)]
        )


def _nodes(ns: str) -> list[GraphNode]:
    return [
        _node(
            ns,
            "eks-prod-cluster",
            NodeType.K8S_CLUSTER,
            "eks-prod-cluster",
            "medium",
            oidc_issuer=_OIDC,
        ),
        _node(
            ns,
            "workloads",
            NodeType.K8S_NAMESPACE,
            "workloads",
            "medium",
            namespace="workloads",
        ),
        _node(
            ns,
            "app-service-account",
            NodeType.K8S_SERVICE_ACCOUNT,
            "app-service-account",
            "high",
            annotations=[f"eks.amazonaws.com/role-arn: {_ROLE_ARN}"],
            role_arn=_ROLE_ARN,
        ),
        _node(
            ns,
            "backend-api-pod",
            NodeType.K8S_POD,
            "backend-api-pod",
            "high",
            service_account="app-service-account",
            token_volume="/var/run/secrets/eks.amazonaws.com/serviceaccount/token",
        ),
        _node(
            ns,
            "EksWorkloadRole",
            NodeType.IAM_ROLE,
            "EksWorkloadRole",
            "critical",
            oidc_provider=_OIDC,
            trust_policy=f"Federated: {_OIDC}",
            actions=["s3:GetObject", "s3:ListBucket"],
        ),
        _node(
            ns,
            "corporate-vault-data",
            NodeType.S3_BUCKET,
            "corporate-vault-data",
            "critical",
            bucket_name="corporate-vault-data",
        ),
        _node(
            ns,
            "CustomerBankingRecords",
            NodeType.DATASET,
            "CustomerBankingRecords",
            "critical",
            classification="restricted",
        ),
    ]


def _edges(ns: str) -> list[GraphEdge]:
    return [
        _edge(ns, "backend-api-pod", "workloads", EdgeType.IN_NAMESPACE, "low"),
        _edge(
            ns,
            "backend-api-pod",
            "app-service-account",
            EdgeType.BINDS_SERVICE_ACCOUNT,
            "high",
        ),
        _edge(ns, "app-service-account", "EksWorkloadRole", EdgeType.FEDERATES_TO, "critical"),
        _edge(ns, "EksWorkloadRole", "corporate-vault-data", EdgeType.CAN_READ, "critical"),
        _edge(
            ns,
            "corporate-vault-data",
            "CustomerBankingRecords",
            EdgeType.STORES_SENSITIVE_DATA,
            "critical",
        ),
    ]


def _findings(ns: str) -> list[ExpectedFinding]:
    return [
        ExpectedFinding(
            id=_nid(ns, "finding-k8s-pod-irsa-exfil-01"),
            severity="critical",
            family=FindingFamily.K8S_POD_IRSA_EXFIL,
            resource_ids=[
                _nid(ns, "backend-api-pod"),
                _nid(ns, "app-service-account"),
                _nid(ns, "EksWorkloadRole"),
                _nid(ns, "corporate-vault-data"),
            ],
            expected_scanner_visibility="visible",
            ground_truth="Workload pod binds IRSA token federated to IAM role reading S3 vault",
            remediation="Scope IAM role permissions and restrict OIDC trust policy conditions",
        ),
    ]


def _critical(ns: str) -> GroundTruthPath:
    return GroundTruthPath(
        id=_nid(ns, "path-critical-k8s-irsa-01"),
        severity="critical",
        nodes=[
            _nid(ns, "backend-api-pod"),
            _nid(ns, "app-service-account"),
            _nid(ns, "EksWorkloadRole"),
            _nid(ns, "corporate-vault-data"),
            _nid(ns, "CustomerBankingRecords"),
        ],
        edges=[
            _ek(ns, "backend-api-pod", EdgeType.BINDS_SERVICE_ACCOUNT, "app-service-account"),
            _ek(ns, "app-service-account", EdgeType.FEDERATES_TO, "EksWorkloadRole"),
            _ek(ns, "EksWorkloadRole", EdgeType.CAN_READ, "corporate-vault-data"),
            _ek(
                ns,
                "corporate-vault-data",
                EdgeType.STORES_SENSITIVE_DATA,
                "CustomerBankingRecords",
            ),
        ],
        explanation=(
            "Pod backend-api-pod projects token federating to EksWorkloadRole to read "
            "CustomerBankingRecords from corporate-vault-data"
        ),
    )
