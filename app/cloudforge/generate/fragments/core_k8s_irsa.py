"""core.k8s_pod_irsa_exfil: a pod's IRSA token walks into AWS IAM and reads S3.

Story: backend-api-pod binds app-service-account, whose annotation federates
into EksWorkloadRole. On the direct chain that role reads the corporate vault
bucket; with ``extra_hops`` it chains by ``sts:AssumeRole`` through intermediate
IAM roles (service account to IAM role to role) and the last one holds the read
grant. With ``dead_end`` the pod also calls a second pod whose service account
carries no cloud annotation.
"""

from __future__ import annotations

from random import Random
from typing import Any

from app.cloudforge.generate.fragments._core import Kit, Piece, draw_hops, hop_lines, shape_of
from app.cloudforge.generate.fragments._vocab import AWS_HOP_ROLES, K8S_DEAD_ENDS
from app.cloudforge.generate.fragments.base import FragmentBundle, register, register_core
from app.cloudforge.models.findings import (
    ExpectedFinding,
    FindingFamily,
    GroundTruthPath,
    SinkKind,
)
from app.cloudforge.models.graph import EdgeType, GraphEdge, GraphNode, NodeTags, NodeType

_TAGS = NodeTags(env="prod", owner="platform-k8s", app="banking-backend")
_ROLE_ARN = "arn:aws:iam::123456789012:role/EksWorkloadRole"
_OIDC = "https://oidc.eks.us-east-1.amazonaws.com/id/EXAMPLED3B761B01042F"
_ENTRY = "backend-api-pod"
_SA = "app-service-account"
_HEAD = "EksWorkloadRole"
_BUCKET = "corporate-vault-data"
_SINK = "customer-banking-records"
_READ_ACTIONS = ["s3:GetObject", "s3:ListBucket"]


@register_core
@register("core.k8s_irsa")
class K8sPodIrsaExfil:
    scenario_type = "k8s_pod_irsa_exfil"
    cloud = "k8s"
    prompt = (
        "A pod in this cluster can talk to cloud IAM. Can that workload identity "
        "reach sensitive data, and is the hop obvious from the estate?"
    )
    checklist = ("k8s_pod_irsa_exfil", "Kubernetes: Pod IRSA Exfiltration")
    teaching_point = "Pod IRSA token -> IAM role -> sensitive S3"

    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        kit = Kit(ns, _TAGS)
        shape = shape_of(params)
        hops = draw_hops(kit, rng, shape.extra_hops, AWS_HOP_ROLES, "role", NodeType.IAM_ROLE)
        chain = [_HEAD, *hops.ids]
        nodes = _nodes(kit, reads=not hops.ids) + hops.nodes
        if hops.nodes:
            hops.nodes[-1].attributes["actions"] = list(_READ_ACTIONS)
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


def _nodes(kit: Kit, *, reads: bool) -> list[GraphNode]:
    head_actions = list(_READ_ACTIONS) if reads else ["sts:AssumeRole"]
    return [
        kit.node(
            "eks-prod-cluster",
            NodeType.K8S_CLUSTER,
            "eks-prod-cluster",
            "medium",
            oidc_issuer=_OIDC,
        ),
        kit.node(
            "workloads", NodeType.K8S_NAMESPACE, "workloads", "medium", namespace="workloads"
        ),
        kit.node(
            _SA,
            NodeType.K8S_SERVICE_ACCOUNT,
            _SA,
            "high",
            annotations=[f"eks.amazonaws.com/role-arn: {_ROLE_ARN}"],
            role_arn=_ROLE_ARN,
        ),
        kit.node(
            _ENTRY,
            NodeType.K8S_POD,
            _ENTRY,
            "high",
            service_account=_SA,
            token_volume="/var/run/secrets/eks.amazonaws.com/serviceaccount/token",
        ),
        kit.node(
            _HEAD,
            NodeType.IAM_ROLE,
            _HEAD,
            "critical",
            oidc_provider=_OIDC,
            trust_policy=f"Federated: {_OIDC}",
            actions=head_actions,
        ),
        kit.node(_BUCKET, NodeType.S3_BUCKET, _BUCKET, "critical", bucket_name=_BUCKET),
        kit.node(_SINK, NodeType.DATASET, _SINK, "critical", classification="restricted"),
    ]


def _edges(kit: Kit, chain: list[str]) -> list[GraphEdge]:
    reader = chain[-1]
    return [
        kit.edge(_ENTRY, "workloads", EdgeType.IN_NAMESPACE, "low"),
        kit.edge(_ENTRY, _SA, EdgeType.BINDS_SERVICE_ACCOUNT, "high"),
        kit.edge(_SA, _HEAD, EdgeType.FEDERATES_TO, "critical"),
        *kit.chain(chain, EdgeType.ASSUMES, "critical"),
        kit.edge(reader, _BUCKET, EdgeType.CAN_READ, "critical"),
        kit.edge(_BUCKET, _SINK, EdgeType.STORES_SENSITIVE_DATA, "critical"),
    ]


def _dead_end(kit: Kit, rng: Random) -> Piece:
    """A pod the entry pod calls, bound to a service account with no annotation."""
    pod_name, sa_name = rng.choice(K8S_DEAD_ENDS)
    return Piece(
        nodes=[
            kit.node(pod_name, NodeType.K8S_POD, pod_name, "low", service_account=sa_name),
            kit.node(
                sa_name, NodeType.K8S_SERVICE_ACCOUNT, sa_name, "low", automount_token="false"
            ),
        ],
        edges=[
            kit.edge(_ENTRY, pod_name, EdgeType.CAN_INVOKE, "low"),
            kit.edge(pod_name, sa_name, EdgeType.BINDS_SERVICE_ACCOUNT, "low"),
        ],
    )


def _findings(kit: Kit, reader: str) -> list[ExpectedFinding]:
    resources = [kit.nid(_ENTRY), kit.nid(_SA), kit.nid(_HEAD), kit.nid(reader), kit.nid(_BUCKET)]
    return [
        ExpectedFinding(
            id=kit.nid("finding-k8s-pod-irsa-exfil-01"),
            severity="critical",
            family=FindingFamily.K8S_POD_IRSA_EXFIL,
            resource_ids=list(dict.fromkeys(resources)),
            expected_scanner_visibility="visible",
            ground_truth="Workload pod binds IRSA token federated to IAM role reading S3 vault",
            remediation="Scope IAM role permissions and restrict OIDC trust policy conditions",
        ),
    ]


def _critical(kit: Kit, chain: list[str], names: list[str]) -> GroundTruthPath:
    reader = chain[-1]
    return GroundTruthPath(
        id=kit.nid("path-critical-k8s-irsa-01"),
        severity="critical",
        nodes=[kit.nid(n) for n in [_ENTRY, _SA, *chain, _BUCKET, _SINK]],
        edges=[
            kit.ek(_ENTRY, EdgeType.BINDS_SERVICE_ACCOUNT, _SA),
            kit.ek(_SA, EdgeType.FEDERATES_TO, _HEAD),
            *kit.chain_keys(chain, EdgeType.ASSUMES),
            kit.ek(reader, EdgeType.CAN_READ, _BUCKET),
            kit.ek(_BUCKET, EdgeType.STORES_SENSITIVE_DATA, _SINK),
        ],
        sink_kind=SinkKind.DATA,
        target=kit.nid(_SINK),
        explanation=(
            f"Pod {_ENTRY} projects a token federating to {_HEAD}"
            + (f"; {hop_lines(names, 'assumes')}" if len(names) > 1 else "")
            + f"; {names[-1]} reads {_SINK} from {_BUCKET}"
        ),
    )
