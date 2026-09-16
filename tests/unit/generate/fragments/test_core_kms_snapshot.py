from random import Random

import app.cloudforge.generate.fragments.core_kms  # noqa: F401
import app.cloudforge.generate.fragments.core_snapshot  # noqa: F401
from app.cloudforge.generate.fragments.base import get_fragment
from app.cloudforge.models.findings import FindingFamily


def test_kms_fragment_finding() -> None:
    bundle = get_fragment("core.kms_key_overbroad").build("k0", Random(0), {})
    assert FindingFamily.KMS_KEY_POLICY_OVERBROAD in {f.family for f in bundle.findings}
    assert all(n.id.startswith("k0/") for n in bundle.nodes)


def test_snapshot_fragment_finding() -> None:
    bundle = get_fragment("core.public_ebs_snapshot").build("s0", Random(0), {})
    assert FindingFamily.EBS_SNAPSHOT_PUBLIC in {f.family for f in bundle.findings}
    ids = {n.id for n in bundle.nodes}
    for finding in bundle.findings:
        assert set(finding.resource_ids) <= ids
