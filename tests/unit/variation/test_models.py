"""Unit tests for ``VariationSpec``/``VariationConstraints``/manifest models."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.cloudforge.io.loaders import load_yaml
from app.cloudforge.variation.models import (
    RunManifest,
    ScenarioManifestEntry,
    ValidationProfile,
    VariationConstraints,
    VariationSpec,
)

_SMOKE = Path("examples/variation/aws_smoke.yaml")


def test_load_smoke_spec() -> None:
    spec = VariationSpec.model_validate(load_yaml(_SMOKE))
    assert spec.families
    assert spec.seed_count >= 1


def test_smoke_spec_has_two_families_and_tiny_scale() -> None:
    spec = VariationSpec.model_validate(load_yaml(_SMOKE))
    assert set(spec.families) == {"ci_cd_iam_chain", "public_data_exposure"}
    assert spec.scale_profiles == ["tiny"]
    assert spec.seed_start == 0
    assert spec.seed_count == 5


def test_constraints_default_no_apply_true() -> None:
    assert VariationConstraints().no_apply is True


def test_constraints_default_no_credentials_true() -> None:
    assert VariationConstraints().no_credentials is True


def test_constraints_default_max_failures_before_abort() -> None:
    assert VariationConstraints().max_failures_before_abort == 25


def test_smoke_spec_constraints_keep_safety_defaults() -> None:
    spec = VariationSpec.model_validate(load_yaml(_SMOKE))
    assert spec.constraints.no_apply is True
    assert spec.constraints.no_credentials is True


def test_variation_spec_rejects_unknown_fields() -> None:
    data = load_yaml(_SMOKE)
    data["bogus_field"] = "nope"
    with pytest.raises(ValidationError):
        VariationSpec.model_validate(data)


def test_variation_constraints_no_apply_cannot_be_disabled() -> None:
    """Safety default is structural: explicitly setting no_apply False is rejected."""
    with pytest.raises(ValidationError):
        VariationConstraints.model_validate({"no_apply": False})


def test_variation_constraints_no_credentials_cannot_be_disabled() -> None:
    with pytest.raises(ValidationError):
        VariationConstraints.model_validate({"no_credentials": False})


def test_validation_profile_fields() -> None:
    profile = ValidationProfile(
        run_validate=True,
        run_report=True,
        run_terraform_validate="if_available",
        run_checkov="if_available",
        run_opa="if_available",
    )
    assert profile.run_validate is True
    assert profile.run_terraform_validate == "if_available"


def test_scenario_manifest_entry_round_trip() -> None:
    entry = ScenarioManifestEntry(
        scenario_id="ci_cd_iam_chain-tiny-0",
        family="ci_cd_iam_chain",
        seed=0,
        scale="tiny",
        axes={"decoy": "1"},
        artifact_dir="scenarios/ci_cd_iam_chain-tiny-0",
        gen_duration_sec=0.01,
        validation_status="pass",
        scanner_status="not_scored",
        failure_id=None,
    )
    assert entry.failure_id is None
    assert entry.model_dump()["scenario_id"] == "ci_cd_iam_chain-tiny-0"


def test_run_manifest_holds_entries() -> None:
    entry = ScenarioManifestEntry(
        scenario_id="s1",
        family="ci_cd_iam_chain",
        seed=0,
        scale="tiny",
        axes={},
        artifact_dir="scenarios/s1",
        gen_duration_sec=0.01,
        validation_status="pass",
        scanner_status="not_scored",
        failure_id=None,
    )
    manifest = RunManifest(run_id="run1", entries=[entry])
    assert manifest.run_id == "run1"
    assert len(manifest.entries) == 1
