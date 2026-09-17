"""``core.public_data_exposure`` fragment: direct public S3 exposure.

Story: a public-read S3 bucket (``customer-pii``) is reachable from the
internet and holds a sensitive customer-PII data set, with no compensating
control. That direct exposure is the critical risk, distinct from the IAM
privilege *chain* of ``core.ci_cd_iam_chain``: no role-assumption hop, the
data is one bucket-policy away from the public. Supporting findings: the
public-read exposure, a missing-logging gap, and one benign false-positive
(a public-looking backups bucket that a bucket policy actually locks down).

Difficulty adds, through the composer's shape: a second public-looking bucket
the account exposes that a policy locks down (``dead_end``), a lookalike
bucket with the same public-read attributes behind a compensating control
(``lookalike``), and an application identity route to the same data
(``prefix_hops``), labeled as its own high-severity path.
"""

from __future__ import annotations

from random import Random
from typing import Any

from app.cloudforge.generate.fragments import _aws_shape as aws
from app.cloudforge.generate.fragments._core import Kit, Piece, shape_of
from app.cloudforge.generate.fragments._vocab import LOOKALIKE_BUCKETS
from app.cloudforge.generate.fragments.base import FragmentBundle, register
from app.cloudforge.models.findings import (
    ExpectedFinding,
    FindingFamily,
    GroundTruthPath,
    SinkKind,
)
from app.cloudforge.models.graph import EdgeType, GraphEdge, GraphNode, NodeTags, NodeType

_TAGS = NodeTags(env="prod", owner="data-platform-team", app="customer-data-lake")
_ENTRY = "acct-main"
_BUCKET = "s3-public-data"
_SINK = "data-customer-pii"


@register("core.public_data_exposure")
class PublicDataExposure:
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
        tail_edges=[kit.ek(_BUCKET, EdgeType.STORES_SENSITIVE_DATA, _SINK)],
        actions=["s3:Get*", "s3:List*"],
        sink_kind=SinkKind.DATA,
        stem="pde",
        dead_end=aws.dead_end_bucket,
    )


def _lookalike(kit: Kit, rng: Random) -> Piece:
    return aws.lookalike(
        kit,
        rng,
        _ENTRY,
        EdgeType.EXPOSED_TO_INTERNET,
        "s3",
        NodeType.S3_BUCKET,
        LOOKALIKE_BUCKETS,
        public_access="enabled",
        acl="public-read",
        logging="disabled",
    )


def _nodes(kit: Kit) -> list[GraphNode]:
    return [
        kit.node(_ENTRY, NodeType.ACCOUNT, "prod-account", "high"),
        kit.node("vpc-prod", NodeType.VPC, "prod-vpc", "low", cidr="10.1.0.0/16"),
        kit.node(
            _BUCKET,
            NodeType.S3_BUCKET,
            "customer-pii",
            "critical",
            public_access="enabled",
            acl="public-read",
            logging="disabled",
        ),
        kit.node(
            "s3-locked-backups",
            NodeType.S3_BUCKET,
            "public-looking-backups",
            "medium",
            public_access="enabled",
            compensating_control="true",
        ),
        kit.node("app-data-lake", NodeType.APPLICATION, "customer-data-lake", "high"),
        kit.node(
            _SINK,
            NodeType.DATASET,
            "customer-pii-records",
            "critical",
            classification="restricted",
        ),
        kit.node("trail-main", NodeType.LOG_TRAIL, "main-trail", "medium"),
    ]


def _edges(kit: Kit) -> list[GraphEdge]:
    return [
        kit.edge(_ENTRY, _BUCKET, EdgeType.EXPOSED_TO_INTERNET, "critical"),
        kit.edge(_BUCKET, _SINK, EdgeType.STORES_SENSITIVE_DATA, "critical"),
        kit.edge(_BUCKET, "app-data-lake", EdgeType.BELONGS_TO_APP, "low"),
        kit.edge("s3-locked-backups", "app-data-lake", EdgeType.BELONGS_TO_APP, "low"),
        kit.edge(_ENTRY, "s3-locked-backups", EdgeType.EXPOSED_TO_INTERNET, "low"),
        # NOTE: no `s3-public-data -> logs_to -> trail-main` edge: the
        # *absence* is the s3_logging_missing finding.
    ]


def _critical(kit: Kit) -> GroundTruthPath:
    return GroundTruthPath(
        id=kit.nid("path-critical-pde-01"),
        severity="critical",
        nodes=[kit.nid(_ENTRY), kit.nid(_BUCKET), kit.nid(_SINK)],
        edges=[
            kit.ek(_ENTRY, EdgeType.EXPOSED_TO_INTERNET, _BUCKET),
            kit.ek(_BUCKET, EdgeType.STORES_SENSITIVE_DATA, _SINK),
        ],
        sink_kind=SinkKind.DATA,
        target=kit.nid(_SINK),
        explanation=(
            "The customer-pii bucket has public-read access with no compensating "
            "control, so it is reachable directly from the internet -> anonymous "
            "read of the sensitive customer-PII dataset it stores."
        ),
    )


def _findings(kit: Kit) -> list[ExpectedFinding]:
    return [_public_exposure_finding(kit), _logging_finding(kit), _false_positive_finding(kit)]


def _public_exposure_finding(kit: Kit) -> ExpectedFinding:
    return ExpectedFinding(
        id=kit.nid("find-pde-public-01"),
        severity="critical",
        family=FindingFamily.S3_PUBLIC_EXPOSURE,
        resource_ids=[kit.nid(_BUCKET), kit.nid(_SINK)],
        expected_scanner_visibility="visible",
        ground_truth="customer-pii allows public read and stores sensitive data.",
        remediation=(
            "Enable S3 Block Public Access and remove the public-read ACL/bucket policy."
        ),
    )


def _logging_finding(kit: Kit) -> ExpectedFinding:
    return ExpectedFinding(
        id=kit.nid("find-pde-logging-01"),
        severity="medium",
        family=FindingFamily.S3_LOGGING_MISSING,
        resource_ids=[kit.nid(_BUCKET), kit.nid("trail-main")],
        expected_scanner_visibility="visible",
        ground_truth="The public bucket has no access logging / CloudTrail data events.",
        remediation="Enable S3 access logging and CloudTrail data events for the bucket.",
    )


def _false_positive_finding(kit: Kit) -> ExpectedFinding:
    return ExpectedFinding(
        id=kit.nid("find-pde-fp-01"),
        severity="low",
        family=FindingFamily.PUBLIC_LOOKING_BUCKET_WITH_COMPENSATING_CONTROL,
        resource_ids=[kit.nid("s3-locked-backups")],
        expected_scanner_visibility="visible",
        ground_truth="benign",
        remediation=(
            "None needed: a bucket policy restricts access despite the public-looking name."
        ),
    )
