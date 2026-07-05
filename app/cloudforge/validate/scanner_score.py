"""Scanner-result scorer: map observed Checkov findings to expected findings.

Turns cloudforge from a scenario *generator* into a benchmark *harness* (gap #10 of
FXL-D003). Checkov emits resource-level AWS-hygiene checks keyed by a Terraform
resource ADDRESS (``aws_iam_role.role_deploy``); our ``expected_findings.json`` are
graph-level risk-chain findings keyed by GRAPH NODE ids (``role-deploy``). These do
not map 1:1, so the scorer inverts the emitter's ``resource_name`` mapping to link a
checkov ``resource`` back to a node, then scores coverage honestly:

* an expected finding is **detected** if a checkov failed-check lands on any of its
  ``resource_ids`` (resource-level match);
* a checkov failed-check that touches no expected finding's resource is an
  **unexpected** finding (an observed false positive relative to the ground truth).

The mismatch is the useful signal — it reveals where a scanner misses graph-level
risk. Fail-soft: no ``checkov.json`` (or unparseable output) -> ``None`` ("not scored").
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from app.cloudforge.io.loaders import dump_json
from app.cloudforge.io.paths import ScenarioPaths
from app.cloudforge.models.findings import ExpectedFindings
from app.cloudforge.models.graph import ScenarioGraph
from app.cloudforge.pipeline.identifiers import resource_name

_SCANNER_NAME = "checkov"
_COVERAGE_PRECISION = 2


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


def score_scenario(paths: ScenarioPaths) -> ScannerScore | None:
    """Score checkov output against expected findings, or ``None`` if not scored.

    Returns ``None`` (fail-soft, never raises) when no ``checkov.json`` exists or its
    content is unparseable — the scenario simply was not scanner-scored.
    """
    failed_resources = _load_failed_resources(paths)
    if failed_resources is None:
        return None
    graph = _load_graph(paths)
    expected = _load_expected(paths)
    if graph is None or expected is None:
        return None
    return _score(graph, expected, failed_resources)


def write_scanner_score(paths: ScenarioPaths) -> Path | None:
    """Compute and persist ``scanner_score.json``; ``None`` when not scored (no write)."""
    score = score_scenario(paths)
    if score is None:
        return None
    dump_json(paths.scanner_score, score.model_dump())
    return paths.scanner_score


def _score(
    graph: ScenarioGraph, expected: ExpectedFindings, failed_resources: list[str]
) -> ScannerScore:
    node_ids = _resource_to_node_ids(graph, failed_resources)
    detected = [f for f in expected.findings if node_ids & set(f.resource_ids)]
    missed = len(expected.findings) - len(detected)
    matched_nodes = {nid for f in detected for nid in f.resource_ids} & node_ids
    unexpected = _unexpected_count(graph, failed_resources, matched_nodes)
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
    )


def _unexpected_count(
    graph: ScenarioGraph, failed_resources: list[str], matched_nodes: set[str]
) -> int:
    """Distinct failed-check resources that map to no expected-finding node."""
    unexpected: set[str] = set()
    for resource in failed_resources:
        node_id = _resolve_node_id(graph, resource)
        if node_id is None or node_id not in matched_nodes:
            unexpected.add(resource)
    return len(unexpected)


def _resource_to_node_ids(graph: ScenarioGraph, failed_resources: list[str]) -> set[str]:
    resolved: set[str] = set()
    for resource in failed_resources:
        node_id = _resolve_node_id(graph, resource)
        if node_id is not None:
            resolved.add(node_id)
    return resolved


def _resolve_node_id(graph: ScenarioGraph, resource: str) -> str | None:
    """Invert the emitter mapping: ``aws_<type>.<label>`` -> graph ``node.id``.

    Strip the ``aws_<type>.`` prefix to the bare Terraform label, then match it against
    ``resource_name(node)`` (the exact transform the emitter applied).
    """
    label = resource.rsplit(".", 1)[-1]
    for node in graph.nodes:
        if resource_name(node) == label:
            return node.id
    return None


def _load_failed_resources(paths: ScenarioPaths) -> list[str] | None:
    """The ``resource`` address of every checkov failed-check, or ``None`` (not scored)."""
    if not paths.checkov_results.exists():
        return None
    try:
        payload = json.loads(paths.checkov_results.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    failed = payload.get("results", {}).get("failed_checks", [])
    if not isinstance(failed, list):
        return None
    return [
        c["resource"] for c in failed if isinstance(c, dict) and isinstance(c.get("resource"), str)
    ]


def _load_graph(paths: ScenarioPaths) -> ScenarioGraph | None:
    data = _safe_read_json(paths.graph)
    if data is None:
        return None
    try:
        return ScenarioGraph.model_validate(data)
    except ValueError:
        return None


def _load_expected(paths: ScenarioPaths) -> ExpectedFindings | None:
    data = _safe_read_json(paths.expected_findings)
    if data is None:
        return None
    try:
        return ExpectedFindings.model_validate(data)
    except ValueError:
        return None


def _safe_read_json(path: Path) -> object | None:
    """Read + parse a JSON file, or ``None`` on any read/parse error (fail-soft)."""
    try:
        parsed: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return parsed
