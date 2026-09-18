"""Scanner-result scorer: map observed Checkov findings to expected findings.

Turns cloudforge from a scenario *generator* into a benchmark *harness* (gap #10 of
the 12-point scenario discipline). Checkov emits resource-level AWS-hygiene checks
keyed by a Terraform resource ADDRESS (``aws_iam_role.role_deploy``); our
``expected_findings.json`` are graph-level risk-chain findings keyed by GRAPH NODE
ids (``role-deploy``). These do
not map 1:1, so the scorer inverts the emitter's ``resource_name`` mapping to link a
checkov ``resource`` back to a node, then scores coverage honestly:

* an expected finding is **detected** if a checkov failed-check lands on any of its
  ``resource_ids`` (resource-level match);
* a checkov failed-check that touches no expected finding's resource is an
  **unexpected** finding (an observed false positive relative to the ground truth).

The mismatch is the useful signal — it reveals where a scanner misses graph-level
risk. Fail-soft (clause S12): no ``checkov.json`` (or unparseable output) -> ``None``
("not scored") — never a crash, never a silently-hidden missed/unexpected finding.

``score_scenario`` returning ``None`` covers two different situations that must not
be reported identically: (a) the scanner genuinely never ran (no ``checkov.json``),
and (b) ``checkov.json`` exists but could not be used (invalid JSON, wrong shape, or
the scenario's own ``graph.json``/``expected_findings.json`` failed to load). See
:mod:`app.cloudforge.validate.scanner_score_diagnostics` for the helper that tells
these apart so a caller (the orchestrator, the report) never prints the same
caveat-free "not scored" message for both.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from app.cloudforge.io.loaders import dump_json
from app.cloudforge.io.paths import ScenarioPaths
from app.cloudforge.models.findings import ExpectedFindings
from app.cloudforge.models.graph import ScenarioGraph
from app.cloudforge.validate.scanner_score_loaders import load_expected, load_graph
from app.cloudforge.validate.scanner_score_matching import (
    resource_to_node_ids,
    unexpected_count,
)

_SCANNER_NAME = "checkov"
_COVERAGE_PRECISION = 2
_MATCH_STRATEGY = "resource-address-to-graph-node"


class ScannerScore(BaseModel):
    """Coverage of a scenario's expected findings by an observed scanner run."""

    model_config = ConfigDict(extra="forbid")

    scanner: str
    expected_findings: int
    matched_findings: int
    missed_findings: int
    unexpected_findings: int
    expected_detected_count: int
    expected_missed_count: int
    false_positive_observed_count: int
    scanner_coverage_score: float
    # Issue #115 metric vocabulary — same values as the fields above, under the
    # names the stress contract asks for, plus the strategy used and any caveats
    # collected while parsing checkov output (never hidden, always surfaced).
    expected_total: int
    matched: int
    missed: int
    unexpected: int
    coverage: float
    match_strategy: str
    warnings: list[str] = []


def score_scenario(paths: ScenarioPaths) -> ScannerScore | None:
    """Score checkov output against expected findings, or ``None`` if not scored.

    Returns ``None`` (fail-soft, never raises) when no ``checkov.json`` exists or its
    content is unusable (invalid JSON / wrong shape) or the scenario's own artifacts
    fail to load — the scenario simply was not scanner-scored. Use
    :func:`app.cloudforge.validate.scanner_score_diagnostics.not_scored_reason` to
    distinguish "never run" from "present but unusable" when ``None`` is returned.
    """
    failed_resources, warnings = _load_failed_resources(paths)
    if failed_resources is None:
        return None
    graph = load_graph(paths)
    expected = load_expected(paths)
    if graph is None or expected is None:
        return None
    return _score(graph, expected, failed_resources, warnings)


def write_scanner_score(paths: ScenarioPaths) -> Path | None:
    """Compute and persist ``scanner_score.json``; ``None`` when not scored (no write)."""
    score = score_scenario(paths)
    if score is None:
        return None
    dump_json(paths.scanner_score, score.model_dump())
    return paths.scanner_score


def _score(
    graph: ScenarioGraph,
    expected: ExpectedFindings,
    failed_resources: list[str],
    warnings: list[str],
) -> ScannerScore:
    node_ids = resource_to_node_ids(graph, failed_resources)
    detected = [f for f in expected.findings if node_ids & set(f.resource_ids)]
    missed = len(expected.findings) - len(detected)
    matched_nodes = {nid for f in detected for nid in f.resource_ids} & node_ids
    unexpected = unexpected_count(graph, failed_resources, matched_nodes)
    total = len(expected.findings)
    coverage = round(len(detected) / total, _COVERAGE_PRECISION) if total else 0.0
    return ScannerScore(
        scanner=_SCANNER_NAME,
        expected_findings=total,
        matched_findings=len(detected),
        missed_findings=missed,
        unexpected_findings=unexpected,
        expected_detected_count=len(detected),
        expected_missed_count=missed,
        false_positive_observed_count=unexpected,
        scanner_coverage_score=coverage,
        expected_total=total,
        matched=len(detected),
        missed=missed,
        unexpected=unexpected,
        coverage=coverage,
        match_strategy=_MATCH_STRATEGY,
        warnings=warnings,
    )


def _load_failed_resources(paths: ScenarioPaths) -> tuple[list[str] | None, list[str]]:
    """The ``resource`` address of every checkov failed-check, plus any warnings.

    Returns ``(None, [])`` only when ``checkov.json`` does not exist, or is present
    but too malformed to score at all (invalid JSON, non-object top level, non-dict
    ``results``, non-list ``failed_checks``) — these remain "not scored", matching
    the documented fail-soft contract;
    ``app.cloudforge.validate.scanner_score_diagnostics.not_scored_reason`` recovers
    *why* for a caller that wants the caveat instead of a bare ``None``. When the
    file IS well-shaped, individual malformed ``failed_checks`` entries (not an
    object, or missing/non-string ``resource``) are skipped rather than silently
    dropped: the skip count is recorded in the returned warnings so a partial/dirty
    scanner run is still scored, and the caveat is never hidden.
    """
    if not paths.checkov_results.exists():
        return None, []
    try:
        payload = json.loads(paths.checkov_results.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, []
    if not isinstance(payload, dict):
        return None, []
    results = payload.get("results", {})
    if not isinstance(results, dict):
        return None, []
    failed = results.get("failed_checks", [])
    if not isinstance(failed, list):
        return None, []

    resources: list[str] = []
    skipped = 0
    for check in failed:
        if isinstance(check, dict) and isinstance(check.get("resource"), str):
            resources.append(check["resource"])
        else:
            skipped += 1

    warnings: list[str] = []
    if skipped:
        noun = "entry" if skipped == 1 else "entries"
        warnings.append(
            f"{skipped} failed_checks {noun} malformed (not an object, or missing/"
            "non-string 'resource') — skipped, not counted as matched or unexpected"
        )
    return resources, warnings
