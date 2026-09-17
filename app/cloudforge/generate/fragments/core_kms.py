"""``core.kms_key_overbroad``: a KMS key policy grants Decrypt to ``*``.

Story: SecretsReader can read the encrypted-exports bucket, and the customer-data-key
that bucket is encrypted with lets any principal decrypt. What the attacker reaches
is the key (``sink_kind`` ``key``): the decrypt capability over what the bucket
holds. The path walks role -> bucket -> key, so the bucket is the resource the key
unlocks, and the customer secrets the bucket stores stay off the graded path.

Difficulty adds, through the composer's shape: a bucket the reader can also read
that holds nothing (``dead_end``), a lookalike key with the same wildcard policy
behind an org-scoped condition (``lookalike``), and an application identity route
to the same key (``prefix_hops``), labeled as its own high-severity path.
"""

from __future__ import annotations

from random import Random
from typing import Any

from app.cloudforge.generate.fragments import _aws_shape as aws
from app.cloudforge.generate.fragments._core import Kit, Piece, shape_of
from app.cloudforge.generate.fragments._vocab import LOOKALIKE_KEYS
from app.cloudforge.generate.fragments.base import FragmentBundle, register_core
from app.cloudforge.models.findings import (
    ExpectedFinding,
    FindingFamily,
    GroundTruthPath,
    SinkKind,
)
from app.cloudforge.models.graph import EdgeType, GraphEdge, GraphNode, NodeTags, NodeType

_TAGS = NodeTags(env="prod", owner="data-platform-team", app="secrets-store")
_ENTRY = "role-reader"
_BUCKET = "s3-encrypted"
_SINK = "kms-data"


@register_core
class KmsKeyOverbroad:
    scenario_type = "kms_key_overbroad"
    cloud = "aws"
    prompt = (
        "A customer data store is encrypted with a KMS key. Who can decrypt with "
        "that key, and what does the key unlock?"
    )
    checklist = ("kms_key_policy_overbroad", "Cryptography: KMS Key Wildcard Decrypt Policy")
    teaching_point = "Wildcard `kms:Decrypt` on a key policy; reaches the key"

    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        kit = Kit(ns, _TAGS)
        extra = aws.extend(kit, rng, shape_of(params), _story(kit), _lookalike)
        return FragmentBundle(
            nodes=_nodes(kit) + extra.nodes,
            edges=_edges(kit) + extra.edges,
            findings=_findings(kit) + extra.findings,
            paths=[_critical(kit), *extra.paths],
        )


def _story(kit: Kit) -> aws.Story:
    return aws.Story(
        entry=_ENTRY,
        resource=_BUCKET,
        tail=[_BUCKET, _SINK],
        tail_edges=[kit.ek(_BUCKET, EdgeType.ENCRYPTED_WITH, _SINK)],
        actions=["s3:Get*", "s3:List*", "kms:Decrypt"],
        sink_kind=SinkKind.KEY,
        stem="kms",
        dead_end=aws.dead_end_readable_bucket,
    )


def _lookalike(kit: Kit, rng: Random) -> Piece:
    return aws.lookalike(
        kit,
        rng,
        _ENTRY,
        EdgeType.CAN_DECRYPT,
        "kms",
        NodeType.KMS_KEY,
        LOOKALIKE_KEYS,
        **aws.conditioned(principal="*", actions=["kms:Decrypt"]),
    )


def _nodes(kit: Kit) -> list[GraphNode]:
    return [
        kit.node("acct-main", NodeType.ACCOUNT, "prod-account", "medium"),
        kit.node(_ENTRY, NodeType.IAM_ROLE, "SecretsReader", "high"),
        kit.node(
            "pol-reader",
            NodeType.IAM_POLICY,
            "SecretsReaderPolicy",
            "high",
            actions=["kms:Decrypt", "s3:Get*", "s3:List*"],
            resource="*",
        ),
        kit.node(
            _SINK,
            NodeType.KMS_KEY,
            "customer-data-key",
            "critical",
            principal="*",
            actions=["kms:Decrypt"],
        ),
        kit.node(_BUCKET, NodeType.S3_BUCKET, "encrypted-exports", "critical", logging="disabled"),
        kit.node(
            "s3-locked-backups",
            NodeType.S3_BUCKET,
            "public-looking-backups",
            "medium",
            public_access="enabled",
            compensating_control="true",
        ),
        kit.node("app-secrets-store", NodeType.APPLICATION, "secrets-store", "medium"),
        kit.node(
            "data-secrets",
            NodeType.DATASET,
            "customer-secrets",
            "critical",
            classification="restricted",
        ),
        kit.node("trail-main", NodeType.LOG_TRAIL, "main-trail", "medium"),
    ]


def _edges(kit: Kit) -> list[GraphEdge]:
    return [
        kit.edge(_ENTRY, "pol-reader", EdgeType.ATTACHED_POLICY, "high"),
        kit.edge(_ENTRY, _SINK, EdgeType.CAN_DECRYPT, "critical"),
        kit.edge(_ENTRY, _BUCKET, EdgeType.CAN_READ, "critical"),
        kit.edge(_BUCKET, _SINK, EdgeType.ENCRYPTED_WITH, "critical"),
        kit.edge(_BUCKET, "data-secrets", EdgeType.STORES_SENSITIVE_DATA, "none"),
        kit.edge(_BUCKET, "app-secrets-store", EdgeType.BELONGS_TO_APP, "low"),
        kit.edge("s3-locked-backups", "app-secrets-store", EdgeType.BELONGS_TO_APP, "low"),
    ]


def _critical(kit: Kit) -> GroundTruthPath:
    return GroundTruthPath(
        id=kit.nid("path-critical-kms-01"),
        severity="critical",
        nodes=[kit.nid(_ENTRY), kit.nid(_BUCKET), kit.nid(_SINK)],
        edges=[
            kit.ek(_ENTRY, EdgeType.CAN_READ, _BUCKET),
            kit.ek(_BUCKET, EdgeType.ENCRYPTED_WITH, _SINK),
        ],
        sink_kind=SinkKind.KEY,
        target=kit.nid(_SINK),
        explanation=(
            "SecretsReader can read encrypted-exports; the bucket is encrypted with "
            "customer-data-key, whose policy grants kms:Decrypt to *, so the reader "
            "holds the decrypt capability over everything the bucket stores."
        ),
    )


def _findings(kit: Kit) -> list[ExpectedFinding]:
    return [_kms_finding(kit), _logging_finding(kit), _fp_finding(kit)]


def _kms_finding(kit: Kit) -> ExpectedFinding:
    return ExpectedFinding(
        id=kit.nid("find-kms-01"),
        severity="critical",
        family=FindingFamily.KMS_KEY_POLICY_OVERBROAD,
        resource_ids=[kit.nid(_SINK), kit.nid(_ENTRY), kit.nid("pol-reader")],
        expected_scanner_visibility="partial",
        ground_truth="KMS key policy allows kms:Decrypt from any AWS principal.",
        remediation="Restrict the key policy principal to the SecretsReader role.",
    )


def _logging_finding(kit: Kit) -> ExpectedFinding:
    return ExpectedFinding(
        id=kit.nid("find-kms-logging-01"),
        severity="medium",
        family=FindingFamily.S3_LOGGING_MISSING,
        resource_ids=[kit.nid(_BUCKET), kit.nid("trail-main")],
        expected_scanner_visibility="visible",
        ground_truth="The encrypted-exports bucket has no access logging.",
        remediation="Enable S3 access logging and CloudTrail data events.",
    )


def _fp_finding(kit: Kit) -> ExpectedFinding:
    return ExpectedFinding(
        id=kit.nid("find-kms-fp-01"),
        severity="low",
        family=FindingFamily.PUBLIC_LOOKING_BUCKET_WITH_COMPENSATING_CONTROL,
        resource_ids=[kit.nid("s3-locked-backups")],
        expected_scanner_visibility="visible",
        ground_truth="benign",
        remediation="None needed: a bucket policy restricts access despite the name.",
    )
