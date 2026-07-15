"""Graph-shape signature + diversity report (design doc §4.2/§5).

``shape_signature`` summarizes a composed ``ScenarioBundle``'s STRUCTURE — sorted
node-type counts, sorted edge-type counts, critical-path length, finding families,
and presence of decoys/false-positives/compensating-controls — as a stable hash.
Display ``name``/``tags`` are never read. The one benign-additive node the
``MutationGenerator`` may inject (``mutation_ops.EXTRA_SUBNET_ID`` + its membership
edge) is canonicalized out before hashing (see ``_shape_nodes``/``_shape_edges``), so
a cosmetic mutation hashes identically to its base for EVERY family — including one
whose base has no Subnet (``public_data_exposure``), where the injected Subnet would
otherwise cross the 0->1 count bucket. Per-type counts are then bucketed (see
``_count_bucket``) so an in-band scale change stays equal while a genuinely different
scale profile or topology still produces a different signature.

``diversity_report`` aggregates a list of ``(family, ScenarioBundle)`` pairs into
the §5 acceptance-gate metrics: unique shape count, critical-path-length spread,
decoy/FP/compensating-control percentages, and an honest ``unsupported_axes`` map
for axes a family structurally cannot vary (never silently skipped).
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter

from app.cloudforge.generate.base import ScenarioBundle
from app.cloudforge.generate.mutation_ops import EXTRA_SUBNET_ID
from app.cloudforge.models.graph import GraphEdge, GraphNode
from app.cloudforge.variation._diversity_report import (
    build_report,
    has_compensating_controls,
    has_decoys,
    has_false_positives,
)

__all__ = [
    "diversity_report",
    "has_compensating_controls",
    "has_decoys",
    "has_false_positives",
    "shape_signature",
]

_BUCKET_THRESHOLDS = (4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096)


def _count_bucket(n: int) -> int:
    """Coarsen a count into a bucket wide enough to absorb the mutation
    engine's one benign-additive node/edge, narrow enough to separate scale
    profiles. 0 stays its own bucket (presence/absence always matters)."""
    if n <= 0:
        return 0
    if n <= 4:
        return 1
    bucket = 1
    for threshold in _BUCKET_THRESHOLDS:
        if n > threshold:
            bucket += 1
        else:
            break
    return bucket


def _type_count_buckets(values: list[str]) -> list[tuple[str, int]]:
    counts = Counter(values)
    return sorted((kind, _count_bucket(n)) for kind, n in counts.items())


def _shape_nodes(bundle: ScenarioBundle) -> list[GraphNode]:
    """Nodes minus the mutation engine's one documented benign-additive node, so a
    cosmetic mutation does not change the shape (its extra Subnet would otherwise cross
    the 0->1 count bucket for any base family lacking a Subnet — e.g. public_data_exposure)."""
    return [n for n in bundle.graph.nodes if n.id != EXTRA_SUBNET_ID]


def _shape_edges(bundle: ScenarioBundle) -> list[GraphEdge]:
    """Edges minus the benign-extra subnet's membership edge (same rationale as
    ``_shape_nodes``). Only the edge originating at the benign node is dropped; the
    ``belongs_to_app`` type itself is load-bearing in both real families."""
    return [e for e in bundle.graph.edges if e.from_ != EXTRA_SUBNET_ID]


def _critical_path_length(bundle: ScenarioBundle) -> int:
    critical = [p for p in bundle.ground_truth.paths if p.severity == "critical"]
    if not critical:
        return 0
    return max(len(p.nodes) for p in critical)


def shape_signature(bundle: ScenarioBundle, family: str) -> str:
    """Stable hash of ``bundle``'s structural shape. Names/tags are excluded."""
    node_types = _type_count_buckets([n.type.value for n in _shape_nodes(bundle)])
    edge_types = _type_count_buckets([e.type.value for e in _shape_edges(bundle)])
    finding_families = sorted({f.family.value for f in bundle.findings.findings})
    payload = {
        "family": family,
        "node_type_buckets": node_types,
        "edge_type_buckets": edge_types,
        "critical_path_length_bucket": _count_bucket(_critical_path_length(bundle)),
        "finding_families": finding_families,
        "has_decoys": has_decoys(bundle),
        "has_false_positives": has_false_positives(bundle),
        "has_compensating_controls": has_compensating_controls(bundle),
    }
    canonical = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def diversity_report(
    bundles: list[tuple[str, ScenarioBundle]], axes: list[str] | None = None
) -> dict[str, object]:
    """Aggregate composed bundles into the §5 diversity metrics."""
    return build_report(bundles, axes or [], shape_signature, _critical_path_length)
