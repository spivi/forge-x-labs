"""The seeded fragment-composition engine (``GraphComposer``).

A sibling of ``TemplateGenerator`` behind the ``ScenarioGenerator`` protocol.
Given ``(spec, seed)`` it draws a deterministic *fragment plan*: one
``core.<family>`` fragment plus decoy / false-positive / compensating-control
counts derived from ``spec.difficulty`` (``spec.variation_axes`` overrides win
per role), then fills with diverse ``benign_noise``, biased toward the low or
high end of the scale profile's node band by the same difficulty, until that
band is met. Every non-core kind is drawn from the vendor pool
``composer_kinds.POOLS[spec.cloud]``, so the padding matches the estate's own
cloud (a Kubernetes estate also gets the AWS pool, since its path federates
into AWS). Every fragment owns its own
namespaced ids, so the assembled graph, findings, and ground truth cannot
disagree; a globally-duplicate id raises ``GraphIntegrityError`` before any
projection. The only randomness is ``Random(seed)``, so the same ``(spec, seed)``
yields byte-identical artifacts.

Ids are role-free on purpose. Node ids are the join key between the student
estate and every instructor artifact, so they are minted here exactly once, for
both trees. Fragments build under a private ``n<NN>_<salt>`` namespace; after
assembly ``composer_ids.retoken`` gives every NODE its own ``n<k>_<salt>`` token
from a seeded permutation over all nodes and rewrites every reference, so neither
a token nor the grouping of tokens says which fragment a node came from. That
provenance lives only in ``GraphNode.origin``, which the student strip never copies.
"""

from __future__ import annotations

from random import Random
from typing import Any

from app.cloudforge.errors import GraphIntegrityError
from app.cloudforge.generate.base import ScenarioBundle
from app.cloudforge.generate.composer_ids import node_ns, retoken
from app.cloudforge.generate.composer_kinds import (
    CORE_KINDS,
    EXTRA_ROLES,
    NOISE_ROLE,
    kinds_for,
    origin_of,
)
from app.cloudforge.generate.fragments import (
    benign_noise,  # noqa: F401
    compensating_control,  # noqa: F401
    core_azure_managed_identity,  # noqa: F401
    core_ci_cd,  # noqa: F401
    core_cross_account,  # noqa: F401
    core_ec2_imds,  # noqa: F401
    core_ecr,  # noqa: F401
    core_gcp_workload_identity,  # noqa: F401
    core_iam_privesc,  # noqa: F401
    core_k8s_irsa,  # noqa: F401
    core_kms,  # noqa: F401
    core_lambda,  # noqa: F401
    core_public_data,  # noqa: F401
    core_rds,  # noqa: F401
    core_secretsmanager,  # noqa: F401
    core_snapshot,  # noqa: F401
    core_sqs,  # noqa: F401
    decoy,  # noqa: F401
    false_positive,  # noqa: F401
    noncore_azure,  # noqa: F401
    noncore_gcp,  # noqa: F401
    noncore_k8s,  # noqa: F401
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

_Plan = list[tuple[str, str, dict[str, Any]]]
_Draft = list[tuple[str, dict[str, Any]]]
# Placeholder namespace used only to count a fragment's nodes while planning.
_COUNT_NS = "plan"

# Per-difficulty extra-fragment counts, keyed by the ``SHORT`` vocabulary
# (``decoy``/``fp``/``ctrl``). A fixed int is used as-is; a ``(lo, hi)`` pair is
# drawn with ``rng.randint``. "medium" is absent on purpose: it keeps today's
# ``rng.randint(1, 3)`` for every kind, which ``_axis_count`` falls back to.
_DIFFICULTY_EXTRA_COUNTS: dict[str, dict[str, int | tuple[int, int]]] = {
    "easy": {"decoy": 1, "fp": 0, "ctrl": 0},
    "hard": {"decoy": 3, "fp": 2, "ctrl": (1, 2)},
}


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
        draft: _Draft = [(self._core_kind(), {"path_hops": rng.randint(3, 5)})]
        for role in EXTRA_ROLES:
            count = self._axis_count(role, rng)
            self._add_extras(draft, self._pool(role), count, rng)
        return self._namespace(self._fill_to_scale(draft, rng))

    def _core_kind(self) -> str:
        return CORE_KINDS.get(self._spec.scenario_type, "core.ci_cd_iam_chain")

    def _pool(self, role: str) -> tuple[str, ...]:
        """The kinds of ``role`` in the spec's vendor pool (``POOLS[spec.cloud]``)."""
        return kinds_for(self._spec.cloud, role)

    def _axis_count(self, role: str, rng: Random) -> int:
        """How many instances of ``role`` to plan: the ``variation_axes`` override,
        else the difficulty table, else ``rng.randint(1, 3)``. Counted per role, so
        the vendor of the kind that fills a slot never changes the count."""
        override = self._spec.variation_axes.get(role)
        if override is not None:
            return max(0, int(override))
        fixed = _DIFFICULTY_EXTRA_COUNTS.get(self._spec.difficulty, {}).get(role)
        if fixed is None:
            return rng.randint(1, 3)
        return rng.randint(*fixed) if isinstance(fixed, tuple) else fixed

    def _add_extras(self, draft: _Draft, kinds: tuple[str, ...], count: int, rng: Random) -> None:
        """Append up to ``count`` instances drawn from ``kinds`` while the plan stays
        under the profile's ``max_nodes`` ceiling (reserving one slot for scale fill).
        Counts the drawn kind's real size: a control mints three nodes."""
        for _ in range(count):
            kind = _pick(rng, kinds)
            planned = self._planned_node_count(draft) + _fragment_size(kind)
            if planned > self._profile.max_nodes - 1:
                return
            draft.append((kind, {}))

    def _fill_to_scale(self, draft: _Draft, rng: Random) -> _Draft:
        """Pad with noise kinds until the seeded target is met. A noise kind may
        mint more than one node (a namespace with its pod), so the fill counts the
        kind's real size and stops rather than overshoot ``max_nodes``."""
        target = rng.randint(*self._noise_target_range())
        noise = self._pool(NOISE_ROLE)
        planned = self._planned_node_count(draft)
        while planned < target:
            kind = _pick(rng, noise)
            size = _fragment_size(kind)
            if planned + size > self._profile.max_nodes:
                break
            draft.append((kind, {}))
            planned += size
        return draft

    def _noise_target_range(self) -> tuple[int, int]:
        """The ``rng.randint`` band ``_fill_to_scale`` draws its node target from.

        "easy" biases toward the profile's low end, "hard" toward its high end;
        "medium" draws from the whole band, same as before difficulty mattered.
        """
        lo, hi = self._profile.min_nodes, self._profile.max_nodes
        third = (hi - lo) // 3
        if self._spec.difficulty == "easy":
            return lo, lo + third
        if self._spec.difficulty == "hard":
            return hi - third, hi
        return lo, hi

    def _planned_node_count(self, draft: _Draft) -> int:
        return sum(_fragment_size(kind, params) for kind, params in draft)

    def _namespace(self, draft: _Draft) -> _Plan:
        """Mint one private namespace per planned fragment.

        Fragments need a namespace so their own edges, findings and paths agree.
        Node ids are re-keyed per node by ``retoken`` afterwards; only path ids and
        finding ids keep this prefix, so it is drawn from a seeded permutation (its
        own stream, like ``_salt``) rather than plan order, and the core fragment
        is not always ``n00``. Seed 0 has no salt and still yields distinct names.
        """
        tokens = list(range(len(draft)))
        Random(self._seed + 211).shuffle(tokens)
        salt = self._salt()
        paired = zip(tokens, draft, strict=True)
        return [(kind, node_ns(token, salt), params) for token, (kind, params) in paired]

    def _assemble(self, plan: _Plan) -> FragmentBundle:
        rng = Random(self._seed)
        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []
        findings: list[ExpectedFinding] = []
        paths: list[GroundTruthPath] = []
        salt = self._salt()
        for kind, ns, params in plan:
            part = get_fragment(kind).build(ns, rng, params)
            for node in part.nodes:
                node.origin = origin_of(kind)
            nodes.extend(part.nodes)
            edges.extend(part.edges)
            findings.extend(part.findings)
            paths.extend(part.paths)
        _assert_unique_ids(nodes)
        _dedupe_names(nodes)
        if salt:
            for node in nodes:
                node.name = f"{node.name}-{salt}"
        bundle = FragmentBundle(nodes=nodes, edges=edges, findings=findings, paths=paths)
        return retoken(bundle, self._seed, salt)

    def _salt(self) -> str:
        if self._seed == 0:
            return ""
        return f"{Random(self._seed + 101).randint(0x1000, 0xFFFF):04x}"


def _fragment_size(kind: str, params: dict[str, Any] | None = None) -> int:
    """How many nodes ``kind`` mints; counted under a throwaway namespace and rng."""
    return len(get_fragment(kind).build(_COUNT_NS, Random(0), params or {}).nodes)


def _pick(rng: Random, kinds: tuple[str, ...]) -> str:
    """One kind from a pool. A one-kind pool spends no rng draw, so a pool with a
    single kind per extra role (the AWS pool) keeps the plan's draw order."""
    if len(kinds) == 1:
        return kinds[0]
    return rng.choice(kinds)


def _assert_unique_ids(nodes: list[GraphNode]) -> None:
    seen: set[str] = set()
    for node in nodes:
        if node.id in seen:
            raise GraphIntegrityError(f"duplicate composed node id: {node.id}")
        seen.add(node.id)


def _dedupe_names(nodes: list[GraphNode]) -> None:
    """Make names unique per node type, in plan order, before the salt is appended.

    Two fragments drawing the same vocabulary name (two IAM roles both called
    ``LegacySupportRole``) would be impossible in a real account and would mark
    both as generated filler. The first keeps its name; later ones get ``-2``,
    ``-3``. Keyed by type so a bucket and the application named after it coexist.
    """
    seen: set[tuple[str, str]] = set()
    for node in nodes:
        base = node.name
        suffix = 1
        while (node.type.value, node.name) in seen:
            suffix += 1
            node.name = f"{base}-{suffix}"
        seen.add((node.type.value, node.name))


class ComposerGenerator:
    """``ScenarioGenerator`` adapter: composes at the protocol's fixed seed 0."""

    def generate(self, spec: ScenarioSpec) -> ScenarioBundle:
        return GraphComposer(spec, seed=0).generate()
