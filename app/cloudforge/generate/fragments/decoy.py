"""``decoy.iam_role_dead_end`` fragment: a risky-looking IAM chain that dead-ends.

Story: an IAM role has a policy attached that reads scary (a broad-looking but
non-destructive action on a scratch bucket ARN), but the chain goes nowhere:
no edge reaches a sensitive sink. A generative/learned engine (or a scanner
under evaluation) must not conflate "looks risky" with "is risky": there is no
``GroundTruthPath`` here, on purpose.

The broad-looking grant (``s3:GetObject``/``s3:ListBucket``, matching
``constants.ALLOWED_BROAD_PATTERNS``) still must be *documented*: the
graph-risk engine's ``_check_broad_grants_documented`` requires every such
grant to be referenced by a finding. The decoy therefore owns one benign,
low-severity finding pointing at its own broad-grant node: it documents the
dead-end policy, it does not assert real risk (no ``GroundTruthPath`` is added).

Ids and names are drawn from ``_vocab.DECOY_IDENTITIES`` and never say "decoy":
they reach the student estate, where the fragment's role must stay invisible.
The composer records that role in ``GraphNode.origin`` for the instructor.
"""

from __future__ import annotations

from random import Random
from typing import Any

from app.cloudforge.generate.fragments._vocab import (
    APP_VALUES,
    DECOY_IDENTITIES,
    ENV_VALUES,
    OWNER_VALUES,
)
from app.cloudforge.generate.fragments.base import FragmentBundle, register
from app.cloudforge.models.findings import ExpectedFinding, FindingFamily
from app.cloudforge.models.graph import (
    EdgeSecurity,
    EdgeType,
    GraphEdge,
    GraphNode,
    NodeSecurity,
    NodeTags,
    NodeType,
)


@register("decoy.iam_role_dead_end")
class DecoyIamRoleDeadEnd:
    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        tags = NodeTags(
            env=rng.choice(ENV_VALUES), owner=rng.choice(OWNER_VALUES), app=rng.choice(APP_VALUES)
        )
        stem, role_name, policy_name, bucket = rng.choice(DECOY_IDENTITIES)
        role_id = f"{ns}/role-{stem}"
        policy_id = f"{ns}/pol-{stem}-read"
        role = GraphNode(
            id=role_id,
            type=NodeType.IAM_ROLE,
            name=role_name,
            tags=tags,
            security=NodeSecurity(criticality="medium"),
        )
        policy = GraphNode(
            id=policy_id,
            type=NodeType.IAM_POLICY,
            name=policy_name,
            tags=tags,
            security=NodeSecurity(criticality="medium"),
            attributes={
                "actions": ["s3:GetObject", "s3:ListBucket"],
                "resource": f"arn:aws:s3:::{bucket}/*",
            },
        )
        attach = GraphEdge(
            from_=role_id,
            to=policy_id,
            type=EdgeType.ATTACHED_POLICY,
            security=EdgeSecurity(risk="low"),
        )
        findings = [_broad_grant_finding(ns, policy_id, policy_name)]
        return FragmentBundle(nodes=[role, policy], edges=[attach], findings=findings, paths=[])


def _broad_grant_finding(ns: str, policy_id: str, policy_name: str) -> ExpectedFinding:
    return ExpectedFinding(
        id=f"{ns}/find-decoy-broad-01",
        severity="low",
        family=FindingFamily.IAM_EXCESSIVE_PRIVILEGE,
        resource_ids=[policy_id],
        expected_scanner_visibility="visible",
        ground_truth=(
            f"benign: {policy_name} grants s3:Get*/List* but is attached to a "
            "dead-end role with no path to any sensitive sink; documents the "
            "broad-looking grant without asserting real risk."
        ),
        remediation="None needed: dead-end decoy; no chain reaches a sensitive resource.",
    )
