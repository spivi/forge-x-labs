import re
from fnmatch import fnmatch
from random import Random

import pytest

import app.cloudforge.generate.fragments.benign_noise  # noqa: F401
import app.cloudforge.generate.fragments.compensating_control  # noqa: F401
import app.cloudforge.generate.fragments.decoy  # noqa: F401
import app.cloudforge.generate.fragments.false_positive  # noqa: F401
import app.cloudforge.generate.fragments.noncore_azure  # noqa: F401
import app.cloudforge.generate.fragments.noncore_gcp  # noqa: F401
import app.cloudforge.generate.fragments.noncore_k8s  # noqa: F401
from app.cloudforge import constants
from app.cloudforge.generate.composer_kinds import AZURE_KINDS, GCP_KINDS, K8S_KINDS, SHORT
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
_AWS_KINDS = (
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
_VENDOR_KINDS = AZURE_KINDS + GCP_KINDS + K8S_KINDS
_NONCORE_KINDS = _AWS_KINDS + _VENDOR_KINDS


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


# --- vendor pools: Azure, GCP, Kubernetes ---------------------------------------


def _vendor_prefix(kind: str) -> str:
    return {"azure": "Azure", "gcp": "Gcp", "k8s": "K8s"}[kind.split(".", 1)[1].split("_", 1)[0]]


@pytest.mark.parametrize("kind", AZURE_KINDS + GCP_KINDS)
def test_azure_and_gcp_fragments_mint_only_their_vendor_types(kind: str) -> None:
    prefix = _vendor_prefix(kind)
    for seed in range(6):
        b = get_fragment(kind).build("x0", Random(seed), {})
        assert b.nodes
        for n in b.nodes:
            assert n.type.value.startswith(prefix), (kind, n.type)


@pytest.mark.parametrize("kind", K8S_KINDS)
def test_k8s_fragments_mint_k8s_types_plus_the_iam_role_they_federate_to(kind: str) -> None:
    for seed in range(6):
        b = get_fragment(kind).build("x0", Random(seed), {})
        assert b.nodes
        for n in b.nodes:
            assert n.type.value.startswith("K8s") or n.type is NodeType.IAM_ROLE, (kind, n.type)


@pytest.mark.parametrize("kind", _VENDOR_KINDS)
def test_vendor_fragments_never_own_a_path_and_keep_their_edges_benign(kind: str) -> None:
    for seed in range(6):
        b = get_fragment(kind).build("x0", Random(seed), {})
        assert b.paths == []
        for e in b.edges:
            assert e.security.risk in ("none", "low"), (kind, e.key)
        for n in b.nodes:
            assert n.security.criticality in ("low", "medium"), (kind, n.id)


@pytest.mark.parametrize("kind", [k for k in _VENDOR_KINDS if SHORT[k] == "noise"])
def test_vendor_noise_has_no_findings(kind: str) -> None:
    b = get_fragment(kind).build("b0", Random(0), {})
    assert b.findings == []


@pytest.mark.parametrize("kind", [k for k in _VENDOR_KINDS if SHORT[k] == "decoy"])
def test_vendor_decoys_dead_end_without_a_sensitive_sink(kind: str) -> None:
    for seed in range(6):
        b = get_fragment(kind).build("d0", Random(seed), {})
        assert len(b.nodes) == 2 and len(b.edges) == 1
        assert all(e.type.value != "stores_sensitive_data" for e in b.edges)
        assert all(n.type is not NodeType.DATASET for n in b.nodes)


def test_k8s_decoy_role_has_no_data_access_and_needs_no_finding() -> None:
    for seed in range(8):
        b = get_fragment("decoy.k8s_irsa_dead_end").build("d0", Random(seed), {})
        role = next(n for n in b.nodes if n.type is NodeType.IAM_ROLE)
        actions = role.attributes["actions"]
        assert isinstance(actions, list) and actions
        for action in actions:
            assert not action.startswith(("s3:", "secretsmanager:", "kms:", "dynamodb:")), action
            assert not any(
                fnmatch(action, pattern) for pattern in constants.ALLOWED_BROAD_PATTERNS
            ), action
        account = next(n for n in b.nodes if n.type is NodeType.K8S_SERVICE_ACCOUNT)
        assert account.attributes["role_arn"] == f"arn:aws:iam::123456789012:role/{role.name}"
        assert b.findings == []


@pytest.mark.parametrize("kind", [k for k in _VENDOR_KINDS if SHORT[k] == "fp"])
def test_vendor_false_positives_own_one_benign_visible_finding(kind: str) -> None:
    b = get_fragment(kind).build("f0", Random(0), {})
    assert len(b.nodes) == 1 and b.edges == []
    assert len(b.findings) == 1
    finding = b.findings[0]
    assert finding.family == FindingFamily.PUBLIC_LOOKING_BUCKET_WITH_COMPENSATING_CONTROL
    assert finding.ground_truth == "benign"
    assert finding.severity == "low"
    assert finding.expected_scanner_visibility == "visible"
    assert finding.resource_ids == [b.nodes[0].id]


def test_azure_false_positive_container_is_private_despite_its_name() -> None:
    b = get_fragment("false_positive.azure_private_container").build("f0", Random(2), {})
    attrs = b.nodes[0].attributes
    assert attrs["access_type"] == "private"
    assert attrs["allow_blob_public_access"] == "false"


def test_gcp_false_positive_bucket_has_uniform_access_and_no_all_users() -> None:
    b = get_fragment("false_positive.gcp_uniform_access_bucket").build("f0", Random(2), {})
    attrs = b.nodes[0].attributes
    assert attrs["uniform_bucket_level_access"] == "true"
    assert attrs["all_users_binding"] == "false"


@pytest.mark.parametrize("kind", [k for k in _VENDOR_KINDS if SHORT[k] == "ctrl"])
def test_vendor_compensating_controls_have_no_finding(kind: str) -> None:
    b = get_fragment(kind).build("cc0", Random(0), {})
    assert b.findings == [] and b.paths == []
    assert len(b.nodes) == 1


def test_azure_compensating_control_blocks_public_reach() -> None:
    b = get_fragment("compensating_control.azure_vault_network_rule").build("c0", Random(1), {})
    attrs = b.nodes[0].attributes
    assert b.nodes[0].type is NodeType.AZURE_KEY_VAULT
    assert attrs["public_network_access"] == "Disabled"
    assert attrs["network_default_action"] == "Deny"
    assert attrs["private_endpoint"] == "true"


def test_gcp_compensating_control_enforces_public_access_prevention() -> None:
    b = get_fragment("compensating_control.gcp_public_access_prevention").build(
        "c0", Random(1), {}
    )
    assert b.nodes[0].type is NodeType.GCP_STORAGE_BUCKET
    assert b.nodes[0].attributes["public_access_prevention"] == "enforced"


@pytest.mark.parametrize("kind", _VENDOR_KINDS)
def test_vendor_fragment_names_vary_with_the_rng_and_ids_follow_names(kind: str) -> None:
    names = set()
    for seed in range(20):
        b = get_fragment(kind).build("v0", Random(seed), {})
        names.add(b.nodes[0].name)
        for n in b.nodes:
            assert n.id == f"v0/{n.name}"
    assert len(names) > 1


@pytest.mark.parametrize("kind", _VENDOR_KINDS)
def test_vendor_fragment_node_count_does_not_depend_on_the_rng(kind: str) -> None:
    """The composer sizes its plan by building each kind once under ``Random(0)``."""
    sizes = {len(get_fragment(kind).build("s0", Random(seed), {}).nodes) for seed in range(10)}
    assert len(sizes) == 1


def test_vendor_names_fit_the_provider_limits() -> None:
    """Key vault names must stay under 24 chars after ``-N`` dedupe and ``-<salt>``."""
    vault_kinds = (
        "benign_noise.azure_config_vault",
        "compensating_control.azure_vault_network_rule",
    )
    for kind in vault_kinds:
        for seed in range(10):
            b = get_fragment(kind).build("l0", Random(seed), {})
            assert len(b.nodes[0].name) + len("-2") + len("-abcd") <= 24, b.nodes[0].name
