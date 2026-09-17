"""Scenario input model tests (check 1: the example scenario loads)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.cloudforge.models.scenario import ScenarioSpec

_VALID = {
    "cloud": "aws",
    "scenario_type": "ci_cd_iam_chain",
    "environment": "staging",
    "difficulty": "medium",
    "company_profile": {"type": "b2b_saas", "size": "small", "app_name": "analytics-exporter"},
    "requirements": {"critical_chains": 1, "medium_findings": 2, "false_positives": 1},
    "constraints": {
        "no_real_secrets": True,
        "no_destructive_permissions": True,
        "max_resources": 40,
        "deployable": False,
    },
}


def test_load_example_scenario_valid_returns_spec(example_spec: ScenarioSpec) -> None:
    assert example_spec.scenario_type == "ci_cd_iam_chain"


def test_scenario_deployable_true_raises() -> None:
    payload = {**_VALID, "constraints": {**_VALID["constraints"], "deployable": True}}

    with pytest.raises(ValidationError):
        ScenarioSpec.model_validate(payload)


def test_scenario_extra_field_forbidden_raises() -> None:
    payload = {**_VALID, "surprise": "nope"}

    with pytest.raises(ValidationError):
        ScenarioSpec.model_validate(payload)


def test_scenario_difficulty_defaults_to_medium() -> None:
    payload = {k: v for k, v in _VALID.items() if k != "difficulty"}
    spec = ScenarioSpec.model_validate(payload)
    assert spec.difficulty == "medium"


@pytest.mark.parametrize("difficulty", ["easy", "medium", "hard"])
def test_scenario_accepts_the_three_valid_difficulties(difficulty: str) -> None:
    payload = {**_VALID, "difficulty": difficulty}
    assert ScenarioSpec.model_validate(payload).difficulty == difficulty


def test_scenario_invalid_difficulty_raises() -> None:
    payload = {**_VALID, "difficulty": "extreme"}

    with pytest.raises(ValidationError):
        ScenarioSpec.model_validate(payload)


def test_scenario_unknown_scenario_type_raises_and_lists_known_families() -> None:
    payload = {**_VALID, "scenario_type": "not_a_real_family"}

    with pytest.raises(ValidationError, match="not_a_real_family") as excinfo:
        ScenarioSpec.model_validate(payload)
    assert "ci_cd_iam_chain" in str(excinfo.value)


@pytest.mark.parametrize(
    "scenario_type",
    [
        "ci_cd_iam_chain",
        "public_data_exposure",
        "cross_account_trust",
        "kms_key_overbroad",
        "public_ebs_snapshot",
        "iam_privesc_policy_version",
        "ec2_imds_credential_exfil",
        "lambda_public_function_url",
        "secretsmanager_policy_overbroad",
        "public_rds_instance",
        "ecr_repository_public_read",
        "sqs_queue_overbroad_policy",
        "k8s_pod_irsa_exfil",
        "azure_imds_keyvault_harvest",
        "gcp_workload_identity_federation",
    ],
)
def test_scenario_every_registered_family_is_a_valid_scenario_type(scenario_type: str) -> None:
    payload = {**_VALID, "scenario_type": scenario_type}
    assert ScenarioSpec.model_validate(payload).scenario_type == scenario_type
