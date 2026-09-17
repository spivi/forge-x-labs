"""Build the Jev state payload from instructor artifacts and student text."""

from __future__ import annotations

from typing import Any

from app.cloudforge.models.findings import ExpectedFindings, GroundTruthPaths
from app.cloudforge.models.graph import ScenarioGraph


def build_judge_state(
    rationale: str,
    graph: ScenarioGraph,
    findings: ExpectedFindings,
    paths: GroundTruthPaths,
) -> dict[str, Any]:
    """Structured context only. Code already owns exact path matching."""
    primary = paths.paths[0] if paths.paths else None
    nodes_by_id = {n.id: n for n in graph.nodes}
    hop_names = []
    if primary:
        hop_names = [nodes_by_id[nid].name for nid in primary.nodes if nid in nodes_by_id]
    return {
        "student": {"rationale": rationale.strip()},
        "ground_truth": {
            "explanation": primary.explanation if primary else "",
            "entry_name": hop_names[0] if hop_names else "",
            "identity_hop": hop_names[1] if len(hop_names) > 1 else "",
            "sink_name": hop_names[-1] if hop_names else "",
            "hop_names": hop_names,
            "finding_families": sorted({f.family.value for f in findings.findings}),
        },
    }
