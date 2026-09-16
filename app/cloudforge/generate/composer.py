"""The seeded fragment-composition engine (``GraphComposer``).

A sibling of ``TemplateGenerator`` behind the ``ScenarioGenerator`` protocol.
Given ``(spec, seed)`` it draws a deterministic *fragment plan* — one
``core.<family>`` fragment plus decoy / false-positive / compensating-control
counts derived from ``spec.variation_axes`` — then fills with ``benign_noise``
until the scale profile's node band is met. Every fragment owns its own
namespaced ids, so the assembled graph, findings, and ground truth cannot
disagree; a globally-duplicate id raises ``GraphIntegrityError`` before any
projection. The only randomness is ``Random(seed)``, so the same ``(spec, seed)``
yields byte-identical artifacts.
"""

from __future__ import annotations

from random import Random
from typing import Any

from app.cloudforge.errors import GraphIntegrityError
from app.cloudforge.generate.base import ScenarioBundle

# Importing the fragment modules registers them in the shared registry (side
# effect) so ``get_fragment`` can resolve every kind the plan may reference.
from app.cloudforge.generate.fragments import (
    benign_noise,  # noqa: F401
    compensating_control,  # noqa: F401
    core_ci_cd,  # noqa: F401
    core_cross_account,  # noqa: F401
    core_ec2_imds,  # noqa: F401
    core_ecr,  # noqa: F401
    core_iam_privesc,  # noqa: F401
    core_kms,  # noqa: F401
    core_lambda,  # noqa: F401
    core_public_data,  # noqa: F401
    core_rds,  # noqa: F401
    core_secretsmanager,  # noqa: F401
    core_snapshot,  # noqa: F401
    core_sqs,  # noqa: F401
    decoy,  # noqa: F401
    false_positive,  # noqa: F401
)
from app.cloudforge.generate.fragments.base import FragmentBundle, get_fragment
from app.cloudforge.generate.scale_profiles import get_profile
from app.cloudforge.models.findings import (
    ExpectedFinding,
    ExpectedFindings,
    GroundTruthPath,
    GroundTruthPaths,
)
from app.cloudforge.models.graph import GraphEdge, GraphNode, ScenarioGraph
from app.cloudforge.models.scenario import ScenarioSpec

_CORE_KINDS = {
    "ci_cd_iam_chain": "core.ci_cd_iam_chain",
    "public_data_exposure": "core.public_data_exposure",
    "cross_account_trust": "core.cross_account_trust",
    "kms_key_overbroad": "core.kms_key_overbroad",
    "public_ebs_snapshot": "core.public_ebs_snapshot",
    "iam_privesc_policy_version": "core.iam_privesc_policy_version",
    "ec2_imds_credential_exfil": "core.ec2_imds_credential_exfil",
    "lambda_public_function_url": "core.lambda_public_function_url",
    "secretsmanager_policy_overbroad": "core.secretsmanager_policy_overbroad",
    "public_rds_instance": "core.public_rds_instance",
    "ecr_repository_public_read": "core.ecr_repository_public_read",
    "sqs_queue_overbroad_policy": "core.sqs_queue_overbroad_policy",
}
_NOISE_KIND = "benign_noise.unrelated_bucket"
_EXTRA_KINDS = (
    "decoy.iam_role_dead_end",
    "false_positive.public_denied_bucket",
    "compensating_control.explicit_deny",
)
_SHORT = {
    "core.ci_cd_iam_chain": "core",
    "core.public_data_exposure": "core",
    "core.cross_account_trust": "core",
    "core.kms_key_overbroad": "core",
    "core.public_ebs_snapshot": "core",
    "core.iam_privesc_policy_version": "core",
    "core.ec2_imds_credential_exfil": "core",
    "core.lambda_public_function_url": "core",
    "core.secretsmanager_policy_overbroad": "core",
    "core.public_rds_instance": "core",
    "core.ecr_repository_public_read": "core",
    "core.sqs_queue_overbroad_policy": "core",
    "decoy.iam_role_dead_end": "decoy",
    "false_positive.public_denied_bucket": "fp",
    "compensating_control.explicit_deny": "ctrl",
    _NOISE_KIND: "noise",
}

_Plan = list[tuple[str, str, dict[str, Any]]]


class GraphComposer:
    """Assembles one scenario from seeded fragments (deterministic per seed)."""

    def __init__(self, spec: ScenarioSpec, seed: int) -> None:
        self._spec = spec
        self._seed = seed
        self._profile = get_profile(spec.scale_profile)

    def generate(self) -> ScenarioBundle:
        merged = self._assemble(self._plan(Random(self._seed)))
        return ScenarioBundle(
            graph=ScenarioGraph(nodes=merged.nodes, edges=merged.edges),
            findings=ExpectedFindings(findings=merged.findings),
            ground_truth=GroundTruthPaths(paths=merged.paths),
        )

    def _plan(self, rng: Random) -> _Plan:
        core = self._core_kind()
        plan: _Plan = [(core, self._ns(core, 0), {"path_hops": rng.randint(3, 5)})]
        for kind in _EXTRA_KINDS:
            self._add_extras(plan, kind, self._axis_count(kind, rng))
        return self._fill_to_scale(plan, rng)

    def _core_kind(self) -> str:
        return _CORE_KINDS.get(self._spec.scenario_type, "core.ci_cd_iam_chain")

    def _axis_count(self, kind: str, rng: Random) -> int:
        override = self._spec.variation_axes.get(_SHORT[kind])
        if override is not None:
            return max(0, int(override))
        return rng.randint(1, 3)

    def _add_extras(self, plan: _Plan, kind: str, count: int) -> None:
        """Append up to ``count`` instances of ``kind`` while the plan stays under
        the profile's ``max_nodes`` ceiling (reserving one slot for scale fill)."""
        for i in range(count):
            if self._planned_node_count(plan) >= self._profile.max_nodes - 1:
                return
            plan.append((kind, self._ns(kind, i), {}))

    def _fill_to_scale(self, plan: _Plan, rng: Random) -> _Plan:
        target = rng.randint(self._profile.min_nodes, self._profile.max_nodes)
        planned = self._planned_node_count(plan)
        index = 0
        while planned < target and planned < self._profile.max_nodes:
            plan.append((_NOISE_KIND, self._ns(_NOISE_KIND, index), {}))
            planned += 1
            index += 1
        return plan

    def _planned_node_count(self, plan: _Plan) -> int:
        rng = Random(0)
        return sum(len(get_fragment(k).build(ns, rng, p).nodes) for k, ns, p in plan)

    def _assemble(self, plan: _Plan) -> FragmentBundle:
        rng = Random(self._seed)
        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []
        findings: list[ExpectedFinding] = []
        paths: list[GroundTruthPath] = []
        for kind, ns, params in plan:
            part = get_fragment(kind).build(ns, rng, params)
            nodes.extend(part.nodes)
            edges.extend(part.edges)
            findings.extend(part.findings)
            paths.extend(part.paths)
        _assert_unique_ids(nodes)
        return FragmentBundle(nodes=nodes, edges=edges, findings=findings, paths=paths)

    def _ns(self, kind: str, index: int) -> str:
        return f"{_SHORT[kind]}{index}"


def _assert_unique_ids(nodes: list[GraphNode]) -> None:
    seen: set[str] = set()
    for node in nodes:
        if node.id in seen:
            raise GraphIntegrityError(f"duplicate composed node id: {node.id}")
        seen.add(node.id)


class ComposerGenerator:
    """``ScenarioGenerator`` adapter: composes at the protocol's fixed seed 0."""

    def generate(self, spec: ScenarioSpec) -> ScenarioBundle:
        return GraphComposer(spec, seed=0).generate()
