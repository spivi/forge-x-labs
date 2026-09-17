import re
from random import Random

import pytest

import app.cloudforge.generate.fragments.benign_noise  # noqa: F401
import app.cloudforge.generate.fragments.compensating_control  # noqa: F401
import app.cloudforge.generate.fragments.decoy  # noqa: F401
import app.cloudforge.generate.fragments.false_positive  # noqa: F401
from app.cloudforge.generate.fragments.base import get_fragment
from app.cloudforge.models.findings import FindingFamily
from app.cloudforge.models.graph import NodeType


def test_decoy_has_no_ground_truth_path():
    b = get_fragment("decoy.iam_role_dead_end").build("d0", Random(0), {})
    assert b.paths == []  # decoys are NOT real risk
    assert b.nodes  # but do add nodes


def test_decoy_documents_its_own_broad_grant():
    b = get_fragment("decoy.iam_role_dead_end").build("d0", Random(0), {})
    policy = next(n for n in b.nodes if n.type == NodeType.IAM_POLICY)
    assert policy.id.startswith("d0/pol-")
    assert any(f.resource_ids == [policy.id] for f in b.findings)


_ROLE_WORDS = re.compile(r"decoy|noise|false.?positive|fp0|honeypot|compensat|control", re.I)
_NONCORE_KINDS = (
    "decoy.iam_role_dead_end",
    "false_positive.public_denied_bucket",
    "compensating_control.explicit_deny",
    "benign_noise.unrelated_bucket",
    "benign_noise.sqs_queue",
    "benign_noise.kms_key",
    "benign_noise.iam_role",
    "benign_noise.ecr_repo",
    "benign_noise.data_set",
    "benign_noise.log_trail",
)


@pytest.mark.parametrize("kind", _NONCORE_KINDS)
def test_noncore_ids_and_names_do_not_say_what_they_are(kind: str) -> None:
    for seed in range(12):
        b = get_fragment(kind).build("x0", Random(seed), {})
        for n in b.nodes:
            assert not _ROLE_WORDS.search(n.id), (kind, n.id)
            assert not _ROLE_WORDS.search(n.name), (kind, n.name)
        for e in b.edges:
            assert not _ROLE_WORDS.search(e.from_) and not _ROLE_WORDS.search(e.to)


def test_decoy_policy_resource_arn_does_not_say_decoy() -> None:
    b = get_fragment("decoy.iam_role_dead_end").build("d0", Random(3), {})
    policy = next(n for n in b.nodes if n.type == NodeType.IAM_POLICY)
    assert "decoy" not in str(policy.attributes["resource"]).lower()


def test_noncore_names_vary_with_the_fragment_rng() -> None:
    names = {
        get_fragment("decoy.iam_role_dead_end").build("d0", Random(seed), {}).nodes[0].name
        for seed in range(20)
    }
    assert len(names) > 1


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
