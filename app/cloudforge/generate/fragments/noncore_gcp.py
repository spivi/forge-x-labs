"""GCP non-core fragments: the ``gcp`` pool's noise, decoy, false positive and
compensating control.

Every node type here already has a workbench zone (``GcpStorageBucket``,
``GcpServiceAccount``, ``GcpProject``, ``GcpFolder``, ``GcpWorkloadIdentityPool``);
the bucket, service account and pool also have Terraform blocks, the project and
folder are structure the core fragment already places without emitting. A compute
instance for batch jobs was the obvious fourth noise kind, but ``GcpComputeInstance``
has neither an emitter block nor a workbench zone, so the pool carries a second
project and a folder instead.

Ids and names come from ``_vocab`` and never say what a fragment is for; the
composer records that in ``GraphNode.origin``. Edges are benign and no fragment
here owns a ground-truth path.
"""

from __future__ import annotations

from random import Random
from typing import Any

from app.cloudforge.generate.fragments._noncore import (
    bundle,
    data_set,
    draw_classification,
    draw_tags,
    edge,
    node,
)
from app.cloudforge.generate.fragments._vocab import (
    GCP_ARTIFACT_BUCKETS,
    GCP_CI_SERVICE_ACCOUNTS,
    GCP_DATA_BUCKETS,
    GCP_DECOY_BINDINGS,
    GCP_FOLDERS,
    GCP_LOCKED_BUCKETS,
    GCP_PARTNER_POOLS,
    GCP_PROJECTS,
    GCP_PUBLIC_LOOKING_BUCKETS,
    SINK_CLASSIFICATION,
)
from app.cloudforge.generate.fragments.base import FragmentBundle, register
from app.cloudforge.models.findings import ExpectedFinding, FindingFamily
from app.cloudforge.models.graph import EdgeType, NodeType

_PROJECT_ID = "prj-analytics-prod-101"


def _sa_email(name: str) -> str:
    return f"{name}@{_PROJECT_ID}.iam.gserviceaccount.com"


@register("benign_noise.gcp_artifact_bucket")
class GcpArtifactBucket:
    """A bucket CI writes build artifacts to."""

    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        name = rng.choice(GCP_ARTIFACT_BUCKETS)
        return bundle(
            [
                node(
                    ns,
                    name,
                    NodeType.GCP_STORAGE_BUCKET,
                    draw_tags(rng),
                    storage_class="STANDARD",
                )
            ]
        )


@register("benign_noise.gcp_bucket_data_set")
class GcpBucketDataSet:
    """A bucket and the data set it holds, at any classification."""

    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        tags = draw_tags(rng)
        bucket_name, data_name = rng.choice(GCP_DATA_BUCKETS)
        bucket = node(ns, bucket_name, NodeType.GCP_STORAGE_BUCKET, tags, storage_class="STANDARD")
        data = data_set(ns, data_name, tags, draw_classification(rng))
        return bundle([bucket, data], [edge(bucket, data, EdgeType.STORES_SENSITIVE_DATA)])


@register("benign_noise.gcp_service_account")
class GcpCiServiceAccount:
    """A service account a CI runner authenticates as."""

    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        name = rng.choice(GCP_CI_SERVICE_ACCOUNTS)
        return bundle(
            [node(ns, name, NodeType.GCP_SERVICE_ACCOUNT, draw_tags(rng), email=_sa_email(name))]
        )


@register("benign_noise.gcp_project")
class GcpSecondProject:
    """A second project next to the one on the path."""

    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        name, project_id = rng.choice(GCP_PROJECTS)
        project = node(ns, name, NodeType.GCP_PROJECT, draw_tags(rng), project_id=project_id)
        return bundle([project])


@register("benign_noise.gcp_folder")
class GcpFolderNoise:
    """A folder in the organization's resource hierarchy."""

    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        name = rng.choice(GCP_FOLDERS)
        return bundle([node(ns, name, NodeType.GCP_FOLDER, draw_tags(rng), display_name=name)])


@register("benign_noise.gcp_workload_identity_pool")
class GcpPartnerPool:
    """A workload identity pool a partner's CI federates through."""

    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        name, issuer = rng.choice(GCP_PARTNER_POOLS)
        return bundle(
            [
                node(
                    ns,
                    name,
                    NodeType.GCP_WORKLOAD_IDENTITY_POOL,
                    draw_tags(rng),
                    issuer_uri=issuer,
                    attribute_condition="assertion.repository_owner == 'partner-org'",
                )
            ]
        )


@register("decoy.gcp_viewer_dead_end")
class GcpViewerDeadEnd:
    """A service account with an object-viewer binding on a bucket that holds
    nothing sensitive: the shape of the core path, no sink."""

    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        tags = draw_tags(rng)
        sa_name, bucket_name = rng.choice(GCP_DECOY_BINDINGS)
        account = node(
            ns,
            sa_name,
            NodeType.GCP_SERVICE_ACCOUNT,
            tags,
            "medium",
            email=_sa_email(sa_name),
            role="roles/storage.objectViewer",
        )
        bucket = node(
            ns,
            bucket_name,
            NodeType.GCP_STORAGE_BUCKET,
            tags,
            storage_class="STANDARD",
        )
        return bundle([account, bucket], [edge(account, bucket, EdgeType.CAN_READ)])


@register("false_positive.gcp_uniform_access_bucket")
class GcpUniformAccessBucket:
    """A bucket named like a public asset bucket that has uniform bucket-level access
    and no ``allUsers`` binding: a scanner keying on the name alone would be wrong."""

    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        name = rng.choice(GCP_PUBLIC_LOOKING_BUCKETS)
        bucket = node(
            ns,
            name,
            NodeType.GCP_STORAGE_BUCKET,
            draw_tags(rng),
            storage_class="STANDARD",
            uniform_bucket_level_access="true",
            all_users_binding="false",
        )
        finding = ExpectedFinding(
            id=f"{ns}/find-fp-gcp-01",
            severity="low",
            family=FindingFamily.PUBLIC_LOOKING_BUCKET_WITH_COMPENSATING_CONTROL,
            resource_ids=[bucket.id],
            expected_scanner_visibility="visible",
            ground_truth="benign",
            remediation=(
                "None needed: uniform bucket-level access is on and no allUsers binding "
                "exists despite the public-looking name."
            ),
        )
        return bundle([bucket], findings=[finding])


@register("compensating_control.gcp_public_access_prevention")
class GcpPublicAccessPrevention:
    """A bucket with public access prevention enforced, holding restricted data.
    No binding can open it and no identity in the estate reaches it, so the
    restricted data set behind it is the core sink's shape with no way in."""

    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        tags = draw_tags(rng)
        bucket_name, data_name = rng.choice(GCP_LOCKED_BUCKETS)
        bucket = node(
            ns,
            bucket_name,
            NodeType.GCP_STORAGE_BUCKET,
            tags,
            "medium",
            storage_class="STANDARD",
            uniform_bucket_level_access="true",
            public_access_prevention="enforced",
        )
        data = data_set(ns, data_name, tags, SINK_CLASSIFICATION, "medium")
        return bundle([bucket, data], [edge(bucket, data, EdgeType.STORES_SENSITIVE_DATA, "none")])
