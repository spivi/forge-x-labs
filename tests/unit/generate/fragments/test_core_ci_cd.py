from random import Random

import app.cloudforge.generate.fragments.core_ci_cd  # noqa: F401 (register side effect)
from app.cloudforge.generate.fragments.base import get_fragment


def _build(hops):
    return get_fragment("core.ci_cd_iam_chain").build("c0", Random(0), {"path_hops": hops})


def test_default_hops_yields_one_critical_path():
    b = _build(3)
    assert len(b.paths) == 1
    assert b.paths[0].severity == "critical"
    # ids are namespaced
    assert all(n.id.startswith("c0/") for n in b.nodes)


def test_more_hops_lengthens_critical_path():
    short = _build(2).paths[0]
    long = _build(5).paths[0]
    assert len(long.nodes) > len(short.nodes)


def test_findings_reference_only_own_nodes():
    b = _build(3)
    node_ids = {n.id for n in b.nodes}
    for f in b.findings:
        assert set(f.resource_ids) <= node_ids


def test_ground_truth_edges_resolve():
    b = _build(4)
    edge_keys = {e.key for e in b.edges}
    for p in b.paths:
        assert set(p.edges) <= edge_keys
