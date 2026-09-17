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
from app.cloudforge.validate import scanner_score, scanner_score_diagnostics

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

    # BUG(medium) S12 regression coverage: a checkov.json that EXISTS but is
    # structurally broken must not be reported with the exact same caveat-free
    # message as "the scanner was never run" — that hides a real problem (a
    # corrupted scanner run looks identical to one that never happened). The
    # report must name checkov.json specifically instead of the generic phrase.
    assert "## Scanner Score" in report
    assert "not scored: no scanner output." not in report
    assert "checkov.json" in report


def test_no_checkov_json_at_all_keeps_generic_not_scored_message(
    generated_scenario: Path,
) -> None:
    paths = ScenarioPaths.from_dir(generated_scenario)
    assert not paths.checkov_results.exists()

    report = ReportRenderer(generated_scenario).render()

    # The TRUE "never ran" case keeps the original generic message — distinct
    # from the structurally-broken-but-present case asserted above.
    assert "## Scanner Score" in report
    assert "not scored: no scanner output." in report


@pytest.mark.parametrize("payload", _STRUCTURALLY_BROKEN_PAYLOADS)
def test_not_scored_reason_distinguishes_present_but_broken(
    generated_scenario: Path, payload: dict[str, object]
) -> None:
    paths = ScenarioPaths.from_dir(generated_scenario)
    paths.checkov_results.parent.mkdir(parents=True, exist_ok=True)
    paths.checkov_results.write_text(json.dumps(payload), encoding="utf-8")

    reason = scanner_score_diagnostics.not_scored_reason(paths)

    assert reason is not None
    assert reason != "no scanner output"
    assert "checkov.json" in reason


def test_not_scored_reason_is_none_when_scored(generated_scenario: Path) -> None:
    paths = ScenarioPaths.from_dir(generated_scenario)
    _write_checkov(paths, _happy_checks())

    assert scanner_score.score_scenario(paths) is not None
    assert scanner_score_diagnostics.not_scored_reason(paths) is None


def test_not_scored_reason_when_no_checkov_json(generated_scenario: Path) -> None:
    paths = ScenarioPaths.from_dir(generated_scenario)
    assert not paths.checkov_results.exists()

    assert scanner_score_diagnostics.not_scored_reason(paths) == "no scanner output"


def test_not_scored_reason_on_invalid_json(generated_scenario: Path) -> None:
    paths = ScenarioPaths.from_dir(generated_scenario)
    paths.checkov_results.parent.mkdir(parents=True, exist_ok=True)
    paths.checkov_results.write_text("{ not json", encoding="utf-8")

    reason = scanner_score_diagnostics.not_scored_reason(paths)

    assert reason is not None
    assert "checkov.json" in reason
    assert "not valid JSON" in reason


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


def test_new_metric_names_mirror_the_legacy_ones(generated_scenario: Path) -> None:
    """Issue #115's requested vocabulary (expected_total/matched/missed/unexpected/
    coverage/match_strategy) is present and consistent with the existing fields."""
    paths = ScenarioPaths.from_dir(generated_scenario)
    _write_checkov(paths, _happy_checks())

    score = scanner_score.score_scenario(paths)

    assert score is not None
    assert score.expected_total == score.expected_findings
    assert score.matched == score.matched_findings
    assert score.missed == score.missed_findings
    assert score.unexpected == score.unexpected_findings
    assert score.coverage == score.scanner_coverage_score
    assert score.match_strategy
    assert isinstance(score.warnings, list)


def test_a_failed_check_on_a_real_but_undocumented_node_counts_unexpected(
    generated_scenario: Path,
) -> None:
    """A failed check resolves to a REAL graph node (``vpc-staging``, present in
    the generated graph but referenced by zero expected findings) — distinct from
    an unresolvable ghost resource, but still counted as unexpected, never hidden
    just because the node exists somewhere in the graph."""
    paths = ScenarioPaths.from_dir(generated_scenario)
    _write_checkov(
        paths,
        [
            *_happy_checks(),
            _failed_check("CKV_AWS_1", "aws_vpc.vpc_staging"),
        ],
    )

    score = scanner_score.score_scenario(paths)

    assert score is not None
    # The 4 documented findings still match exactly as in the happy path...
    assert score.matched_findings == 4
    assert score.missed_findings == 1
    # ...and the vpc-staging check is a REAL node but touches no expected finding
    # -> counted as unexpected via the resolved-node branch, not the ghost-address one.
    assert score.unexpected_findings == 1


def test_graph_json_corrupt_but_checkov_valid_is_not_scored(generated_scenario: Path) -> None:
    """checkov.json is perfectly fine; the scenario's OWN graph.json is corrupt.

    This must not be reported as "scanner never ran" — the scanner DID run and
    produced usable output; it's the product's own artifact that is broken.
    """
    paths = ScenarioPaths.from_dir(generated_scenario)
    _write_checkov(paths, _happy_checks())
    paths.graph.write_text("{ truncated", encoding="utf-8")

    assert scanner_score.score_scenario(paths) is None
    reason = scanner_score_diagnostics.not_scored_reason(paths)
    assert reason == "checkov.json present but graph.json could not be loaded"


def test_expected_findings_json_valid_json_but_fails_model_validation(
    generated_scenario: Path,
) -> None:
    """expected_findings.json parses as JSON but violates the model schema
    (extra="forbid" rejects an unknown field) -> ValueError from Pydantic, caught."""
    paths = ScenarioPaths.from_dir(generated_scenario)
    _write_checkov(paths, _happy_checks())
    broken = {"findings": [{"unexpected_extra_field": "not part of the schema"}]}
    paths.expected_findings.write_text(json.dumps(broken), encoding="utf-8")

    assert scanner_score.score_scenario(paths) is None
    reason = scanner_score_diagnostics.not_scored_reason(paths)
    assert reason == "checkov.json present but expected_findings.json could not be loaded"


def test_expected_findings_json_corrupt_but_checkov_and_graph_valid_is_not_scored(
    generated_scenario: Path,
) -> None:
    paths = ScenarioPaths.from_dir(generated_scenario)
    _write_checkov(paths, _happy_checks())
    paths.expected_findings.write_text("{ truncated", encoding="utf-8")

    assert scanner_score.score_scenario(paths) is None
    reason = scanner_score_diagnostics.not_scored_reason(paths)
    assert reason == "checkov.json present but expected_findings.json could not be loaded"


def test_graph_json_valid_json_but_fails_model_validation(generated_scenario: Path) -> None:
    """graph.json parses as JSON but violates the ScenarioGraph schema (an edge
    referencing a node that does not exist) -> ValueError from Pydantic, caught."""
    paths = ScenarioPaths.from_dir(generated_scenario)
    _write_checkov(paths, _happy_checks())
    paths.graph.write_text(json.dumps({"nodes": [], "edges": []}), encoding="utf-8")
    # Valid ScenarioGraph shape (empty), so this actually loads -> re-break it
    # with a genuinely invalid edge referencing a missing node.
    broken = {
        "nodes": [],
        "edges": [
            {"from": "ghost-a", "to": "ghost-b", "type": "assumes", "security": {"risk": "low"}}
        ],
    }
    paths.graph.write_text(json.dumps(broken), encoding="utf-8")

    assert scanner_score.score_scenario(paths) is None
    reason = scanner_score_diagnostics.not_scored_reason(paths)
    assert reason == "checkov.json present but graph.json could not be loaded"
