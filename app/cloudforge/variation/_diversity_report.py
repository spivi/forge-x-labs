"""Report-aggregation helpers for ``diversity.py`` (kept separate: module-size rule).

Pure functions over already-composed bundles; no generation, no I/O, no cloud
credentials — this module only reads ``ScenarioBundle`` artifacts.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable

from app.cloudforge.generate.base import ScenarioBundle

type _SignatureFn = Callable[[ScenarioBundle, str], str]
type _PathLenFn = Callable[[ScenarioBundle], int]
_MIN_SAMPLES_FOR_AXIS_CHECK = 2


def has_decoys(bundle: ScenarioBundle) -> bool:
    return any(n.id.split("/", 1)[0].startswith("decoy") for n in bundle.graph.nodes)


def has_false_positives(bundle: ScenarioBundle) -> bool:
    return any(f.ground_truth == "benign" for f in bundle.findings.findings)


def has_compensating_controls(bundle: ScenarioBundle) -> bool:
    return any(n.id.split("/", 1)[0].startswith("ctrl") for n in bundle.graph.nodes)


def build_report(
    bundles: list[tuple[str, ScenarioBundle]],
    axes: list[str],
    signature_fn: _SignatureFn,
    path_len_fn: _PathLenFn,
) -> dict[str, object]:
    if not bundles:
        return _empty_report()
    signatures = [signature_fn(b, family) for family, b in bundles]
    path_lengths = [path_len_fn(b) for _family, b in bundles]
    return {
        "total_scenarios": len(bundles),
        "unique_graph_shapes": len(set(signatures)),
        "critical_path_lengths": sorted(set(path_lengths)),
        "scanner_score_profiles": _scanner_score_profiles(),
        "pct_with_decoys": _pct(bundles, has_decoys),
        "pct_with_false_positives": _pct(bundles, has_false_positives),
        "pct_with_compensating_controls": _pct(bundles, has_compensating_controls),
        "families": sorted({family for family, _b in bundles}),
        "unsupported_axes": _unsupported_axes(bundles, axes, path_len_fn),
    }


def _empty_report() -> dict[str, object]:
    return {
        "total_scenarios": 0,
        "unique_graph_shapes": 0,
        "critical_path_lengths": [],
        "scanner_score_profiles": _scanner_score_profiles(),
        "pct_with_decoys": 0.0,
        "pct_with_false_positives": 0.0,
        "pct_with_compensating_controls": 0.0,
        "families": [],
        "unsupported_axes": {},
    }


def _pct(
    bundles: list[tuple[str, ScenarioBundle]], predicate: Callable[[ScenarioBundle], bool]
) -> float:
    if not bundles:
        return 0.0
    hits = sum(1 for _family, b in bundles if predicate(b))
    return round(100.0 * hits / len(bundles), 2)


def _scanner_score_profiles() -> list[str]:
    """Scanner scoring runs in the suite runner (FXL-VAR-1e), not here; this
    harness-layer report marks the dimension WARN-style 'not_scored' rather
    than silently omitting it (never collapse WARN into a fake PASS/FAIL)."""
    return ["not_scored"]


def _unsupported_axes(
    bundles: list[tuple[str, ScenarioBundle]], axes: list[str], path_len_fn: _PathLenFn
) -> dict[str, list[str]]:
    by_family: dict[str, list[ScenarioBundle]] = defaultdict(list)
    for family, bundle in bundles:
        by_family[family].append(bundle)
    result: dict[str, list[str]] = {}
    for family, family_bundles in by_family.items():
        gaps = _axis_gaps(family_bundles, axes, path_len_fn)
        if gaps:
            result[family] = gaps
    return result


def _axis_gaps(
    family_bundles: list[ScenarioBundle], axes: list[str], path_len_fn: _PathLenFn
) -> list[str]:
    gaps: list[str] = []
    if "path_length" in axes and _lacks_variance(family_bundles, path_len_fn):
        gaps.append("path_length")
    return gaps


def _lacks_variance(bundles: list[ScenarioBundle], path_len_fn: _PathLenFn) -> bool:
    if len(bundles) < _MIN_SAMPLES_FOR_AXIS_CHECK:
        return False
    lengths = Counter(path_len_fn(b) for b in bundles)
    return len(lengths) <= 1
