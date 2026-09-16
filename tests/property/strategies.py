"""Shared Hypothesis strategies for graph / ground-truth / finding property tests.

Builds valid and adversarially-mutated ``ScenarioGraph`` / ``GroundTruthPath`` /
``ExpectedFinding`` shapes on top of the REAL models (``app.cloudforge.models.graph``,
``app.cloudforge.models.findings``) and the REAL generators (``ci_cd_iam_chain``,
``public_data_exposure``) so every property test exercises the same object graph
production code depends on rather than a parallel fake.

Kept as plain functions (not `@st.composite` everywhere) so each family's test module
can compose the exact mutation it needs without a combinatorial strategy tree.
"""

from __future__ import annotations

from typing import Protocol

from hypothesis import strategies as st

from app.cloudforge.generate import (
    ci_cd_iam_chain,
    cross_account_trust,
    ec2_imds_credential_exfil,
    ecr_repository_public_read,
    iam_privesc_policy_version,
    kms_key_overbroad,
    lambda_public_function_url,
    public_data_exposure,
    public_ebs_snapshot,
    public_rds_instance,
    secretsmanager_policy_overbroad,
    sqs_queue_overbroad_policy,
)
from app.cloudforge.generate.base import ScenarioBundle
from app.cloudforge.models.findings import (
    ExpectedFinding,
    ExpectedFindings,
    FindingFamily,
    GroundTruthPath,
    GroundTruthPaths,
)
from app.cloudforge.models.graph import (
    EdgeRisk,
    EdgeSecurity,
    EdgeType,
    GraphEdge,
    GraphNode,
    NodeSecurity,
    NodeTags,
    NodeType,
    ScenarioGraph,
)
from app.cloudforge.models.scenario import (
    CompanyProfile,
    Constraints,
    Requirements,
    ScenarioSpec,
)

# --- generous spec (never trips resource-budget / critical-chain-count checks,
# which are NOT part of S4/S5/S6/S7 and would otherwise confound results) --------

GENEROUS_SPEC = ScenarioSpec(
    cloud="aws",
    scenario_type="ci_cd_iam_chain",
    environment="test",
    difficulty="medium",
    company_profile=CompanyProfile(type="b2b_saas", size="small", app_name="prop-test"),
    requirements=Requirements(critical_chains=0, medium_findings=0, false_positives=0),
    constraints=Constraints(
        no_real_secrets=True,
        no_destructive_permissions=True,
        max_resources=10_000,
        deployable=False,
    ),
)


class _ScenarioBuilderModule(Protocol):
    """Structural shape shared by ``ci_cd_iam_chain`` and ``public_data_exposure``."""

    def build_graph(self) -> ScenarioGraph: ...
    def build_findings(self) -> ExpectedFindings: ...
    def build_ground_truth(self) -> GroundTruthPaths: ...


# Real, valid bundles from the two shipped generators — the ground truth for
# "what a self-consistent bundle looks like" that every mutation strategy starts from.
REAL_BUILDERS: tuple[_ScenarioBuilderModule, ...] = (
    ci_cd_iam_chain,
    public_data_exposure,
    cross_account_trust,
    kms_key_overbroad,
    public_ebs_snapshot,
    iam_privesc_policy_version,
    ec2_imds_credential_exfil,
    lambda_public_function_url,
    secretsmanager_policy_overbroad,
    public_rds_instance,
    ecr_repository_public_read,
    sqs_queue_overbroad_policy,
)  # type: ignore[assignment]


def real_bundle(builder: _ScenarioBuilderModule) -> ScenarioBundle:
    return ScenarioBundle(
        graph=builder.build_graph(),
        findings=builder.build_findings(),
        ground_truth=builder.build_ground_truth(),
    )


@st.composite
def real_bundles(draw: st.DrawFn) -> ScenarioBundle:
    """One of the two real, shipped, self-consistent scenario bundles."""
    builder = draw(st.sampled_from(REAL_BUILDERS))
    return real_bundle(builder)


# --- id / name atoms --------------------------------------------------------------

# Deliberately narrow (identifier-shaped) alphabet: this suite stresses graph/finding
# *referential* invariants (S4/S5/S6/S7), not string-sink HCL injection (that is the
# security corpus's job — tests/security/). Keeping ids identifier-shaped means a
# rejection always traces to a referential-integrity clause, never accidental
# Pydantic field-shape noise.
_ID_ALPHABET = st.characters(whitelist_categories=("Ll", "Lu", "Nd"), whitelist_characters="-_")

node_ids = st.text(alphabet=_ID_ALPHABET, min_size=1, max_size=12).map(lambda s: f"n-{s}")
extra_node_ids = st.text(alphabet=_ID_ALPHABET, min_size=1, max_size=12).map(lambda s: f"x-{s}")
names = st.text(alphabet=_ID_ALPHABET, min_size=1, max_size=16).map(lambda s: f"name-{s}")
finding_ids = st.text(alphabet=_ID_ALPHABET, min_size=1, max_size=12).map(lambda s: f"f-{s}")

node_types = st.sampled_from(list(NodeType))
edge_types = st.sampled_from(list(EdgeType))
criticalities = st.sampled_from(["low", "medium", "high", "critical"])
_EDGE_RISK_VALUES: list[EdgeRisk] = ["none", "low", "medium", "high", "critical"]
edge_risks: st.SearchStrategy[EdgeRisk] = st.sampled_from(_EDGE_RISK_VALUES)
severities = st.sampled_from(["low", "medium", "high", "critical"])
scanner_visibilities = st.sampled_from(["visible", "partial", "invisible"])
finding_families = st.sampled_from(list(FindingFamily))

_TAGS = NodeTags(env="test", owner="prop-team", app="prop-app")


def make_node(node_id: str, node_type: NodeType, name: str, crit: str) -> GraphNode:
    return GraphNode(
        id=node_id,
        type=node_type,
        name=name,
        tags=_TAGS,
        security=NodeSecurity(criticality=crit),  # type: ignore[arg-type]
    )


def make_edge(src: str, dst: str, edge_type: EdgeType, risk: str) -> GraphEdge:
    return GraphEdge(from_=src, to=dst, type=edge_type, security=EdgeSecurity(risk=risk))  # type: ignore[arg-type]


@st.composite
def valid_node_lists(draw: st.DrawFn, min_size: int = 2, max_size: int = 8) -> list[GraphNode]:
    """A list of GraphNodes with distinct, hypothesis-generated ids."""
    ids = draw(
        st.lists(node_ids, min_size=min_size, max_size=max_size, unique=True),
    )
    nodes = []
    for nid in ids:
        node_type = draw(node_types)
        name = draw(names)
        crit = draw(criticalities)
        nodes.append(make_node(nid, node_type, name, crit))
    return nodes


@st.composite
def valid_graphs(draw: st.DrawFn) -> ScenarioGraph:
    """A graph with edges that only ever reference existing node ids (S4-clean)."""
    nodes = draw(valid_node_lists(min_size=2, max_size=8))
    ids = [n.id for n in nodes]
    edges = []
    n_edges = draw(st.integers(min_value=0, max_value=len(ids) * 2))
    for _ in range(n_edges):
        src = draw(st.sampled_from(ids))
        dst = draw(st.sampled_from(ids))
        edge_type = draw(edge_types)
        risk = draw(edge_risks)
        edges.append(make_edge(src, dst, edge_type, risk))
    return ScenarioGraph(nodes=nodes, edges=edges)


def bundle_for(
    graph: ScenarioGraph,
    ground_truth: GroundTruthPaths | None = None,
    findings: ExpectedFindings | None = None,
) -> ScenarioBundle:
    return ScenarioBundle(
        graph=graph,
        findings=findings if findings is not None else ExpectedFindings(findings=[]),
        ground_truth=ground_truth if ground_truth is not None else GroundTruthPaths(paths=[]),
    )


__all__ = [
    "GENEROUS_SPEC",
    "REAL_BUILDERS",
    "ExpectedFinding",
    "GroundTruthPath",
    "bundle_for",
    "criticalities",
    "edge_risks",
    "edge_types",
    "extra_node_ids",
    "finding_families",
    "finding_ids",
    "make_edge",
    "make_node",
    "names",
    "node_ids",
    "node_types",
    "real_bundle",
    "real_bundles",
    "scanner_visibilities",
    "severities",
    "valid_graphs",
    "valid_node_lists",
]
