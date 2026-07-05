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
