from random import Random

import app.cloudforge.generate.fragments.core_public_data  # noqa: F401
from app.cloudforge.generate.fragments.base import get_fragment


def test_builds_public_exposure_finding():
    b = get_fragment("core.public_data_exposure").build("p0", Random(0), {})
    fams = {f.family for f in b.findings}
    from app.cloudforge.models.findings import FindingFamily

    assert FindingFamily.S3_PUBLIC_EXPOSURE in fams
    assert all(n.id.startswith("p0/") for n in b.nodes)


def test_findings_reference_only_own_nodes():
    b = get_fragment("core.public_data_exposure").build("p0", Random(0), {})
    ids = {n.id for n in b.nodes}
    for f in b.findings:
        assert set(f.resource_ids) <= ids
