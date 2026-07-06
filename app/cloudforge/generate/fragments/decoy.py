"""``decoy.iam_role_dead_end`` fragment — a risky-looking IAM chain that dead-ends.

Story: an IAM role has a policy attached that reads scary (a broad-looking but
non-destructive action on a decoy resource ARN), but the chain goes nowhere —
no edge reaches a sensitive sink. A generative/learned engine (or a scanner
under evaluation) must not conflate "looks risky" with "is risky": there is no
``GroundTruthPath`` here, on purpose.

The broad-looking grant (``s3:GetObject``/``s3:ListBucket``, matching
``constants.ALLOWED_BROAD_PATTERNS``) still must be *documented* — the
graph-risk engine's ``_check_broad_grants_documented`` requires every such
grant to be referenced by a finding. The decoy therefore owns one benign,
low-severity finding pointing at its own broad-grant node: it documents the
decoy's dead-end policy, it does not assert real risk (no ``GroundTruthPath``
is added).
"""

from __future__ import annotations

from random import Random
from typing import Any

from app.cloudforge.generate.fragments._vocab import APP_VALUES, ENV_VALUES, OWNER_VALUES
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
        role = GraphNode(
            id=f"{ns}/role-decoy",
            type=NodeType.IAM_ROLE,
            name="DecoyRole",
            tags=tags,
            security=NodeSecurity(criticality="medium"),
        )
        policy = GraphNode(
            id=f"{ns}/pol-decoy-broad",
            type=NodeType.IAM_POLICY,
            name="DecoyBroadPolicy",
            tags=tags,
            security=NodeSecurity(criticality="medium"),
            attributes={
                "actions": ["s3:GetObject", "s3:ListBucket"],
                "resource": "arn:aws:s3:::decoy-scratch-bucket/*",
            },
        )
        attach = GraphEdge(
            from_=f"{ns}/role-decoy",
            to=f"{ns}/pol-decoy-broad",
            type=EdgeType.ATTACHED_POLICY,
            security=EdgeSecurity(risk="low"),
        )
        findings = [_broad_grant_finding(ns)]
        return FragmentBundle(nodes=[role, policy], edges=[attach], findings=findings, paths=[])


def _broad_grant_finding(ns: str) -> ExpectedFinding:
    return ExpectedFinding(
        id=f"{ns}/find-decoy-broad-01",
        severity="low",
        family=FindingFamily.IAM_EXCESSIVE_PRIVILEGE,
        resource_ids=[f"{ns}/pol-decoy-broad"],
        expected_scanner_visibility="visible",
        ground_truth=(
            "benign — DecoyBroadPolicy grants s3:Get*/List* but is attached to a "
            "dead-end role with no path to any sensitive sink; documents the "
            "broad-looking grant without asserting real risk."
        ),
        remediation="None needed — dead-end decoy; no chain reaches a sensitive resource.",
    )
