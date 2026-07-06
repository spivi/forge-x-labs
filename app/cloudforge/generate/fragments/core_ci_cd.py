"""``core.ci_cd_iam_chain`` fragment — parameterized CI/CD-to-data IAM chain.

Story: a GitHub Actions OIDC identity assumes a DeployRole, which can
``iam:PassRole`` a chain of intermediate roles (``path_hops - 3`` extra hops)
before reaching a RuntimeRole that holds broad S3 read over a sensitive
customer-exports bucket. That chain is the critical risk. Supporting findings:
an overly-broad S3 read, a missing-logging gap, an over-exposed security
group, and one benign false-positive (a public-looking bucket with a
compensating control).

Ported from the legacy ``generate/ci_cd_iam_chain.py`` hardcoded generator;
every id is namespaced by ``ns`` so composed bundles stay self-consistent.
Node/edge builders live in ``core_ci_cd_nodes.py`` to respect the module/
function size limits (rules/general.md).
"""

from __future__ import annotations

from random import Random
from typing import Any

from app.cloudforge.generate.fragments import core_ci_cd_nodes as parts
from app.cloudforge.generate.fragments.base import FragmentBundle, register
from app.cloudforge.models.findings import ExpectedFinding, FindingFamily, GroundTruthPath
from app.cloudforge.models.graph import EdgeType

_DEFAULT_HOPS = 3


def _extra_hops(hops: int) -> int:
    """Extra intermediate roles inserted between deploy and runtime roles."""
    return max(0, hops - _DEFAULT_HOPS)


@register("core.ci_cd_iam_chain")
class CiCdIamChain:
    def build(self, ns: str, rng: Random, params: dict[str, Any]) -> FragmentBundle:
        hops = int(params.get("path_hops", _DEFAULT_HOPS))
        extra = _extra_hops(hops)
        nodes = parts.fixed_nodes(ns) + parts.hop_nodes(ns, extra)
        edges = parts.fixed_edges(ns) + parts.pass_role_chain(ns, extra)
        findings = _findings(ns, extra)
        path = _critical(ns, extra)
        return FragmentBundle(nodes=nodes, edges=edges, findings=findings, paths=[path])


def _role_chain(extra: int) -> list[str]:
    return ["role-deploy", *[parts.hop_role_id(i) for i in range(extra)], "role-runtime"]


def _critical(ns: str, extra: int) -> GroundTruthPath:
    role_chain = _role_chain(extra)
    nodes = ["cicd-github", *role_chain, "s3-customer-exports", "data-customer-exports"]
    edges = [f"{ns}/cicd-github->{EdgeType.ASSUMES.value}->{ns}/role-deploy"]
    for i in range(len(role_chain) - 1):
        edges.append(
            f"{ns}/{role_chain[i]}->{EdgeType.CAN_PASS_ROLE.value}->{ns}/{role_chain[i + 1]}"
        )
    edges.append(f"{ns}/role-runtime->{EdgeType.CAN_READ.value}->{ns}/s3-customer-exports")
    edges.append(
        f"{ns}/s3-customer-exports->{EdgeType.STORES_SENSITIVE_DATA.value}"
        f"->{ns}/data-customer-exports"
    )
    return GroundTruthPath(
        id=f"{ns}/path-critical-01",
        severity="critical",
        nodes=[f"{ns}/{n}" for n in nodes],
        edges=edges,
        explanation=(
            "GitHub Actions OIDC assumes DeployRole; DeployRole can iam:PassRole "
            "(via any intermediate hops) RuntimeRole; RuntimeRole holds broad "
            "s3:Get*/List* on the sensitive customer-exports bucket -> full read "
            "of customer data via CI."
        ),
    )


def _findings(ns: str, extra: int) -> list[ExpectedFinding]:
    chain_ids = [f"{ns}/{step}" for step in _role_chain(extra)[:-1]]
    return [
        _passrole_finding(ns, chain_ids),
        _excessive_finding(ns),
        _logging_finding(ns),
        _sg_finding(ns),
        _false_positive_finding(ns),
    ]


def _passrole_finding(ns: str, chain_ids: list[str]) -> ExpectedFinding:
    return ExpectedFinding(
        id=f"{ns}/find-passrole-01",
        severity="critical",
        family=FindingFamily.IAM_PASSROLE_RISK,
        resource_ids=[*chain_ids, f"{ns}/role-runtime", f"{ns}/pol-deploy-passrole"],
        expected_scanner_visibility="partial",
        ground_truth="DeployRole can pass RuntimeRole, completing the CI-to-data chain.",
        remediation="Scope iam:PassRole to the exact RuntimeRole ARN and add a role condition.",
    )


def _excessive_finding(ns: str) -> ExpectedFinding:
    return ExpectedFinding(
        id=f"{ns}/find-s3read-01",
        severity="high",
        family=FindingFamily.IAM_EXCESSIVE_PRIVILEGE,
        resource_ids=[
            f"{ns}/role-runtime",
            f"{ns}/pol-runtime-s3read",
            f"{ns}/s3-customer-exports",
        ],
        expected_scanner_visibility="visible",
        ground_truth="RuntimeRole has broader S3 read than intended over the exports bucket.",
        remediation="Replace s3:Get*/List* wildcards with least-privilege object prefixes.",
    )


def _logging_finding(ns: str) -> ExpectedFinding:
    return ExpectedFinding(
        id=f"{ns}/find-logging-01",
        severity="medium",
        family=FindingFamily.S3_LOGGING_MISSING,
        resource_ids=[f"{ns}/s3-customer-exports", f"{ns}/trail-main"],
        expected_scanner_visibility="visible",
        ground_truth="The sensitive bucket has no access logging / CloudTrail data events.",
        remediation="Enable S3 access logging and CloudTrail data events for the bucket.",
    )


def _sg_finding(ns: str) -> ExpectedFinding:
    return ExpectedFinding(
        id=f"{ns}/find-sg-01",
        severity="medium",
        family=FindingFamily.SECURITY_GROUP_OVEREXPOSED,
        resource_ids=[f"{ns}/sg-web", f"{ns}/subnet-public-a"],
        expected_scanner_visibility="visible",
        ground_truth="web-sg allows ingress from 0.0.0.0/0.",
        remediation="Restrict ingress from 0.0.0.0/0 to known corporate/CI CIDRs.",
    )


def _false_positive_finding(ns: str) -> ExpectedFinding:
    return ExpectedFinding(
        id=f"{ns}/find-fp-01",
        severity="low",
        family=FindingFamily.PUBLIC_LOOKING_BUCKET_WITH_COMPENSATING_CONTROL,
        resource_ids=[f"{ns}/s3-public-assets"],
        expected_scanner_visibility="visible",
        ground_truth="benign",
        remediation=(
            "None needed — public read is intentional; a bucket policy limits it to GetObject."
        ),
    )
