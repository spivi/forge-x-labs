"""``cloudforge_scenario`` adapter — ingest existing ``out/<scenario>`` dirs.

Reads a scenario dir (or a parent dir of scenario dirs) produced by ``cloudforge
generate``: ``scenario.yaml`` / ``graph.json`` / ``expected_findings.json`` /
``ground_truth_paths.json`` — already validated/self-consistent, so this adapter
reuses the product models/loaders rather than re-parsing JSON/YAML by hand (design
§8, adapter 1). One ``RawPatternRecord`` is emitted per scenario dir, keyed on its
most severe ground-truth path: title from ``scenario_type``, summary from the
path's explanation, resource types from the nodes it visits, severity from the
path, remediation from overlapping findings. Confidence 0.85; ``full_reuse``.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from app.cloudforge.errors import CloudforgeError, ScenarioLoadError
from app.cloudforge.io.loaders import load_json, load_yaml
from app.cloudforge.io.paths import ScenarioPaths
from app.cloudforge.learn.pattern_enums import CloudProvider
from app.cloudforge.learn.pattern_models import PatternProvenance, RawPatternRecord
from app.cloudforge.learn.source_models import SourceEntry
from app.cloudforge.models.findings import (
    ExpectedFinding,
    ExpectedFindings,
    GroundTruthPath,
    GroundTruthPaths,
)
from app.cloudforge.models.graph import ScenarioGraph
from app.cloudforge.models.scenario import ScenarioSpec

ADAPTER_NAME = "cloudforge_scenario"
ADAPTER_VERSION = "0.1.0"
NORMALIZER_VERSION = "0.1.0"
_EXTRACTION_METHOD = "scenario_dir"
_DEFAULT_CONFIDENCE = 0.85


class ScenarioAdapterError(CloudforgeError):
    """A scenario directory is missing, incomplete, or fails to load for ingestion."""


def _is_scenario_dir(candidate: Path) -> bool:
    """A dir is a scenario dir iff it has a ``scenario.yaml`` of its own."""
    return ScenarioPaths.from_dir(candidate).scenario_yaml.is_file()


def _discover_scenario_dirs(raw_path: Path) -> list[Path]:
    """Return every scenario dir under ``raw_path`` (itself, or its children)."""
    if not raw_path.is_dir():
        raise ScenarioAdapterError(f"scenario source path is not a dir: {raw_path}")

    if _is_scenario_dir(raw_path):
        return [raw_path]

    return sorted(
        child for child in raw_path.iterdir() if child.is_dir() and _is_scenario_dir(child)
    )


def _load_scenario_artifacts(
    paths: ScenarioPaths,
) -> tuple[ScenarioSpec, ScenarioGraph, ExpectedFindings, GroundTruthPaths]:
    """Load the four scenario artifacts via the existing loaders/models."""
    try:
        scenario = ScenarioSpec.model_validate(load_yaml(paths.scenario_yaml))
        graph = ScenarioGraph.model_validate(load_json(paths.graph))
        findings = ExpectedFindings.model_validate(load_json(paths.expected_findings))
        ground_truth = GroundTruthPaths.model_validate(load_json(paths.ground_truth_paths))
    except ScenarioLoadError as exc:
        raise ScenarioAdapterError(f"incomplete scenario dir {paths.base}: {exc}") from exc
    except ValueError as exc:  # pydantic ValidationError subclasses ValueError.
        raise ScenarioAdapterError(f"invalid scenario artifacts in {paths.base}: {exc}") from exc
    return scenario, graph, findings, ground_truth


_SEVERITY_RANK: dict[str, int] = {"critical": 3, "high": 2, "medium": 1, "low": 0}


def _select_critical_path(ground_truth: GroundTruthPaths, scenario_dir: Path) -> GroundTruthPath:
    """Return the most severe ground-truth path (critical first, else first path)."""
    if not ground_truth.paths:
        raise ScenarioAdapterError(f"scenario dir {scenario_dir} has no ground-truth paths")
    return max(ground_truth.paths, key=lambda p: _SEVERITY_RANK.get(p.severity, -1))


def _resource_types_on_path(graph: ScenarioGraph, node_ids: list[str]) -> list[str]:
    """Return the sorted, deduped node types the path visits (normalized names)."""
    wanted = set(node_ids)
    types = {node.type.value for node in graph.nodes if node.id in wanted}
    return sorted(types)


def _remediation_for_path(findings: list[ExpectedFinding], node_ids: list[str]) -> str:
    """Join the (deduped) remediations of findings whose ``resource_ids`` hit the path."""
    wanted = set(node_ids)
    seen: list[str] = []
    for finding in findings:
        if wanted.intersection(finding.resource_ids) and finding.remediation not in seen:
            seen.append(finding.remediation)
    return " ".join(seen)


def _content_hash(*payloads: dict[str, object]) -> str:
    """A stable sha256 over the combined, sorted-key JSON of every artifact payload."""
    digest = hashlib.sha256()
    for payload in payloads:
        digest.update(json.dumps(payload, sort_keys=True).encode("utf-8"))
    return digest.hexdigest()


def _build_raw_payload(
    graph: ScenarioGraph,
    findings: ExpectedFindings,
    path: GroundTruthPath,
) -> dict[str, str | list[str]]:
    """Serialize graph/findings/path into the raw payload (JSON strings; field is typed loose)."""
    return {
        "graph": json.dumps(graph.model_dump(mode="json"), sort_keys=True),
        "expected_findings": json.dumps(findings.model_dump(mode="json"), sort_keys=True),
        "ground_truth_path": json.dumps(path.model_dump(mode="json"), sort_keys=True),
    }


def _build_provenance(
    source: SourceEntry, content_hash: str, extracted_at: datetime
) -> PatternProvenance:
    """Stamp full provenance (design §7); read straight off disk so fetched==extracted."""
    return PatternProvenance(
        source_id=source.id,
        source_name=source.name,
        source_type=source.type,
        source_url_or_path=source.location,
        source_license=source.license,
        reuse_status=source.reuse_status,
        allowed_for_training=source.allowed_for_training,
        extraction_method=_EXTRACTION_METHOD,
        fetched_at=extracted_at,
        extracted_at=extracted_at,
        content_hash=content_hash,
        adapter_name=ADAPTER_NAME,
        adapter_version=ADAPTER_VERSION,
        normalizer_version=NORMALIZER_VERSION,
        confidence=_DEFAULT_CONFIDENCE,
        notes="cloudforge's own validated scenario output; full_reuse.",
    )


def _build_record(
    source: SourceEntry, scenario_dir: Path, extracted_at: datetime
) -> RawPatternRecord:
    """Build the one ``RawPatternRecord`` for a single scenario dir."""
    paths = ScenarioPaths.from_dir(scenario_dir)
    scenario, graph, findings, ground_truth = _load_scenario_artifacts(paths)

    critical_path = _select_critical_path(ground_truth, scenario_dir)
    resource_types = _resource_types_on_path(graph, critical_path.nodes)
    remediation = _remediation_for_path(findings.findings, critical_path.nodes)

    content_hash = _content_hash(
        graph.model_dump(mode="json"),
        findings.model_dump(mode="json"),
        ground_truth.model_dump(mode="json"),
    )

    return RawPatternRecord(
        source_id=source.id,
        raw_id=critical_path.id,
        title=f"{scenario.scenario_type} — {critical_path.severity} risk path",
        summary=critical_path.explanation,
        cloud_provider=CloudProvider(scenario.cloud),
        resource_types=resource_types,
        rule_id=None,
        severity=critical_path.severity,
        category=scenario.scenario_type,
        remediation=remediation,
        references=[],
        raw_payload=_build_raw_payload(graph, findings, critical_path),
        provenance=_build_provenance(source, content_hash, extracted_at),
    )


class CloudforgeScenarioAdapter:
    """``PatternAdapter`` that ingests existing ``out/<scenario>`` dirs (design §8, #1)."""

    adapter_name = ADAPTER_NAME
    adapter_version = ADAPTER_VERSION

    def extract(self, source: SourceEntry, raw_path: Path) -> list[RawPatternRecord]:
        """Extract one record per scenario dir under ``raw_path`` (itself or its children).

        Raises ``ScenarioAdapterError`` if ``raw_path`` doesn't exist, or a discovered
        scenario dir is missing/has invalid artifacts.
        """
        extracted_at = datetime.now(UTC)
        scenario_dirs = _discover_scenario_dirs(raw_path)
        return [_build_record(source, d, extracted_at) for d in scenario_dirs]
