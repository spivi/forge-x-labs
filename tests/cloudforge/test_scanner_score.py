"""Scanner-scorer tests: expected↔observed matching with MOCKED checkov output.

These never invoke real checkov — the on-disk ``checkov.json`` is written from an
in-repo fixture so the score is deterministic and CI-safe. The fixture mirrors the
real shape (``results.failed_checks[].resource`` = a Terraform resource address).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.cloudforge.io.paths import ScenarioPaths
from app.cloudforge.report.renderer import ReportRenderer
from app.cloudforge.validate import scanner_score

# Terraform resource address -> the checkov ``resource`` field. The scorer strips the
# ``aws_<type>.`` prefix and matches the remaining label against ``resource_name(node)``.
_ROLE_DEPLOY = "aws_iam_role.role_deploy"
_ROLE_RUNTIME = "aws_iam_role.role_runtime"
_SG_WEB = "aws_security_group.sg_web"
_S3_PUBLIC_POLICY = "aws_s3_bucket_policy.s3_public_assets"
_S3_CUSTOMER = "aws_s3_bucket.s3_customer_exports"


def _failed_check(check_id: str, resource: str) -> dict[str, str]:
    return {"check_id": check_id, "resource": resource, "check_name": check_id, "file_path": "/x"}


def _write_checkov(paths: ScenarioPaths, failed: list[dict[str, str]]) -> None:
    payload = {"results": {"failed_checks": failed, "passed_checks": []}}
    paths.checkov_results.parent.mkdir(parents=True, exist_ok=True)
    paths.checkov_results.write_text(json.dumps(payload), encoding="utf-8")


def _happy_checks() -> list[dict[str, str]]:
    """Mirrors the real captured sample: 5 failed checks over 4 distinct resources."""
    return [
        _failed_check("CKV_AWS_60", _ROLE_DEPLOY),
        _failed_check("CKV_AWS_60", _ROLE_RUNTIME),
        _failed_check("CKV_AWS_23", _SG_WEB),
        _failed_check("CKV_AWS_382", _SG_WEB),
        _failed_check("CKV_AWS_70", _S3_PUBLIC_POLICY),
    ]


def test_happy_path_matches_real_sample_numbers(generated_scenario: Path) -> None:
    paths = ScenarioPaths.from_dir(generated_scenario)
    _write_checkov(paths, _happy_checks())

    score = scanner_score.score_scenario(paths)

    assert score is not None
    # 5 expected findings; 4 have a checkov failed-check on one of their resources
    # (passrole via role-deploy, s3read via role-runtime, sg via sg-web, fp via
    # s3-public-assets); only find-logging-01 (s3-customer-exports, trail-main) is missed.
    assert score.expected_findings == 5
    assert score.matched_findings == 4
    assert score.missed_findings == 1
    assert score.expected_detected_count == 4
    assert score.expected_missed_count == 1
    # Every failed check maps to a node inside some expected finding -> no false positives.
    assert score.unexpected_findings == 0
    assert score.false_positive_observed_count == 0
    assert score.scanner_coverage_score == 0.8
    assert score.scanner == "checkov"


def test_no_checkov_json_reports_not_scored(generated_scenario: Path) -> None:
    paths = ScenarioPaths.from_dir(generated_scenario)
    # No checkov.json written.
    assert scanner_score.score_scenario(paths) is None


def test_all_matched_gives_full_coverage(generated_scenario: Path) -> None:
    paths = ScenarioPaths.from_dir(generated_scenario)
    # One failed check per expected finding's touchable resource.
    _write_checkov(
        paths,
        [
            _failed_check("CKV_AWS_60", _ROLE_DEPLOY),  # passrole
            _failed_check("CKV_AWS_1", _S3_CUSTOMER),  # s3read + logging
            _failed_check("CKV_AWS_23", _SG_WEB),  # sg
            _failed_check("CKV_AWS_70", _S3_PUBLIC_POLICY),  # fp
        ],
    )

    score = scanner_score.score_scenario(paths)

    assert score is not None
    assert score.matched_findings == 5
    assert score.missed_findings == 0
    assert score.unexpected_findings == 0
    assert score.scanner_coverage_score == 1.0


def test_all_missed_gives_zero_coverage(generated_scenario: Path) -> None:
    paths = ScenarioPaths.from_dir(generated_scenario)
    # A failed check on a resource that maps to NO graph node -> unexpected, no match.
    _write_checkov(paths, [_failed_check("CKV_AWS_99", "aws_iam_role.ghost_role")])

    score = scanner_score.score_scenario(paths)

    assert score is not None
    assert score.matched_findings == 0
    assert score.missed_findings == 5
    assert score.scanner_coverage_score == 0.0
    assert score.unexpected_findings == 1
    assert score.false_positive_observed_count == 1


def test_empty_failed_checks_all_missed_no_false_positives(generated_scenario: Path) -> None:
    paths = ScenarioPaths.from_dir(generated_scenario)
    _write_checkov(paths, [])

    score = scanner_score.score_scenario(paths)

    assert score is not None
    assert score.matched_findings == 0
    assert score.missed_findings == 5
    assert score.unexpected_findings == 0
    assert score.scanner_coverage_score == 0.0


def test_malformed_checkov_json_is_fail_soft(generated_scenario: Path) -> None:
    paths = ScenarioPaths.from_dir(generated_scenario)
    paths.checkov_results.parent.mkdir(parents=True, exist_ok=True)
    paths.checkov_results.write_text("{ not json", encoding="utf-8")

    # Never crash on garbage scanner output — treat as "not scored".
    assert scanner_score.score_scenario(paths) is None


# Valid JSON but a structurally-unexpected shape — e.g. a truncated/interrupted checkov
# write or a scanner error object. The chained ``.get`` on a non-dict ``results`` (or a
# non-list ``failed_checks``) must NOT raise: fail-soft to None ("not scored").
_STRUCTURALLY_BROKEN_PAYLOADS = [
    {"results": None},
    {"results": 42},
    {"results": {"failed_checks": None}},
    {"results": {"failed_checks": 7}},
    {"results": []},
]


@pytest.mark.parametrize("payload", _STRUCTURALLY_BROKEN_PAYLOADS)
def test_non_dict_results_is_fail_soft_not_raise(
    generated_scenario: Path, payload: dict[str, object]
) -> None:
    paths = ScenarioPaths.from_dir(generated_scenario)
    paths.checkov_results.parent.mkdir(parents=True, exist_ok=True)
    paths.checkov_results.write_text(json.dumps(payload), encoding="utf-8")

    # score_scenario is documented to never raise; a structurally-broken shape -> None.
    assert scanner_score.score_scenario(paths) is None


@pytest.mark.parametrize("payload", _STRUCTURALLY_BROKEN_PAYLOADS)
def test_render_is_fail_soft_on_structurally_broken_checkov(
    generated_scenario: Path, payload: dict[str, object]
) -> None:
    paths = ScenarioPaths.from_dir(generated_scenario)
    paths.checkov_results.parent.mkdir(parents=True, exist_ok=True)
    paths.checkov_results.write_text(json.dumps(payload), encoding="utf-8")

    # The report path calls score_scenario — it must not crash on such input.
    report = ReportRenderer(generated_scenario).render()

    assert "## Scanner Score" in report
    assert "not scored — no scanner output." in report


def test_score_to_file_writes_json(generated_scenario: Path) -> None:
    paths = ScenarioPaths.from_dir(generated_scenario)
    _write_checkov(paths, _happy_checks())

    written = scanner_score.write_scanner_score(paths)

    assert written is not None
    assert written.exists()
    on_disk = json.loads(written.read_text(encoding="utf-8"))
    assert on_disk["scanner"] == "checkov"
    assert on_disk["matched_findings"] == 4
    assert on_disk["scanner_coverage_score"] == 0.8


def test_write_scanner_score_returns_none_when_not_scored(generated_scenario: Path) -> None:
    paths = ScenarioPaths.from_dir(generated_scenario)

    assert scanner_score.write_scanner_score(paths) is None
    assert not paths.scanner_score.exists()
