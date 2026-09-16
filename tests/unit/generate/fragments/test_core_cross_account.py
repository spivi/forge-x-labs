from random import Random

import app.cloudforge.generate.fragments.core_cross_account  # noqa: F401
from app.cloudforge.generate.fragments.base import get_fragment
from app.cloudforge.models.findings import FindingFamily


def test_builds_cross_account_finding() -> None:
    bundle = get_fragment("core.cross_account_trust").build("x0", Random(0), {})
    fams = {f.family for f in bundle.findings}
    assert FindingFamily.IAM_CROSS_ACCOUNT_TRUST in fams
    assert all(n.id.startswith("x0/") for n in bundle.nodes)


def test_findings_and_paths_reference_only_own_nodes() -> None:
    bundle = get_fragment("core.cross_account_trust").build("x0", Random(0), {})
    ids = {n.id for n in bundle.nodes}
    keys = {e.key for e in bundle.edges}
    for finding in bundle.findings:
        assert set(finding.resource_ids) <= ids
    for path in bundle.paths:
        assert set(path.nodes) <= ids
        assert set(path.edges) <= keys
