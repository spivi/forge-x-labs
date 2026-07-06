from random import Random

import app.cloudforge.generate.fragments.benign_noise  # noqa: F401
import app.cloudforge.generate.fragments.compensating_control  # noqa: F401
import app.cloudforge.generate.fragments.decoy  # noqa: F401
import app.cloudforge.generate.fragments.false_positive  # noqa: F401
from app.cloudforge.generate.fragments.base import get_fragment
from app.cloudforge.models.findings import FindingFamily


def test_decoy_has_no_ground_truth_path():
    b = get_fragment("decoy.iam_role_dead_end").build("d0", Random(0), {})
    assert b.paths == []  # decoys are NOT real risk
    assert b.nodes  # but do add nodes


def test_false_positive_owns_benign_finding():
    b = get_fragment("false_positive.public_denied_bucket").build("f0", Random(0), {})
    assert any(f.ground_truth == "benign" for f in b.findings)
    assert all(
        f.family == FindingFamily.PUBLIC_LOOKING_BUCKET_WITH_COMPENSATING_CONTROL
        for f in b.findings
    )


def test_benign_noise_has_no_findings_no_paths():
    b = get_fragment("benign_noise.unrelated_bucket").build("b0", Random(0), {})
    assert b.findings == [] and b.paths == []


def test_compensating_control_has_no_finding():
    b = get_fragment("compensating_control.explicit_deny").build("cc0", Random(0), {})
    assert b.findings == []
