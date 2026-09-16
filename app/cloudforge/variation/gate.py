"""Diversity acceptance gate — thresholds ARE the generator-depth test.

A 0-FAIL suite that misses these thresholds is ``cosmetic variation only``,
never success (design doc §5 / FXL-VAR-1g). Optional scanners (checkov
absent → ``scanner_score_profiles == ["not_scored"]``) are WARN, not FAIL.
An axis a family cannot vary is ``unsupported``, not a failed threshold.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

_COSMETIC_ONLY = "cosmetic variation only"
_NOT_SCORED = "not_scored"
_PATH_LENGTH = "path_length"
_SCANNER_KEY = "scanner_score_profiles"


class GateThresholds(BaseModel):
    """The §5 depth bar. Defaults are the design-doc numbers."""

    model_config = ConfigDict(extra="forbid")

    min_shapes: int = 5
    min_path_lengths: int = 4
    min_scanner_profiles: int = 3
    min_decoy_pct: float = 20.0
    min_control_pct: float = 20.0
    min_fp_pct: float = 10.0


class GateResult(BaseModel):
    """Outcome of ``evaluate_gate``. ``passed`` is false iff ``failures`` is nonempty."""

    model_config = ConfigDict(extra="forbid")

    passed: bool
    failures: list[str] = Field(default_factory=list)
    unsupported: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class _Metric:
    name: str
    actual: float
    minimum: float


@dataclass
class _Notes:
    failures: list[str]
    warnings: list[str]


def evaluate_gate(
    report: dict[str, object], thresholds: GateThresholds | None = None
) -> GateResult:
    """Score a live ``diversity_report.json`` (or an equivalent dict) against the bar."""
    bar = thresholds if thresholds is not None else GateThresholds()
    notes = _Notes(failures=[], warnings=[])
    unsupported = _unsupported_axes(report)
    _record_shortfall(_shape_metric(report, bar), notes.failures)
    if _PATH_LENGTH not in unsupported:
        _record_shortfall(_path_metric(report, bar), notes.failures)
    _check_scanner(report, bar, notes)
    _record_shortfall(_pct_metric(report, "pct_with_decoys", bar.min_decoy_pct), notes.failures)
    _record_shortfall(
        _pct_metric(report, "pct_with_compensating_controls", bar.min_control_pct), notes.failures
    )
    _record_shortfall(
        _pct_metric(report, "pct_with_false_positives", bar.min_fp_pct), notes.failures
    )
    return GateResult(
        passed=not notes.failures,
        failures=notes.failures,
        unsupported=unsupported,
        warnings=notes.warnings,
    )


def cosmetic_message() -> str:
    """The exact phrase the CLI prints on a failed gate (ticket AC)."""
    return _COSMETIC_ONLY


def _record_shortfall(metric: _Metric, failures: list[str]) -> None:
    if metric.actual < metric.minimum:
        failures.append(f"{metric.name}: {metric.actual} < {metric.minimum}")


def _shape_metric(report: dict[str, object], bar: GateThresholds) -> _Metric:
    actual = _as_float(report.get("unique_graph_shapes"))
    return _Metric("unique_graph_shapes", actual, bar.min_shapes)


def _path_metric(report: dict[str, object], bar: GateThresholds) -> _Metric:
    lengths = report.get("critical_path_lengths") or []
    count = len(lengths) if isinstance(lengths, list) else 0
    return _Metric("critical_path_lengths", float(count), float(bar.min_path_lengths))


def _pct_metric(report: dict[str, object], key: str, minimum: float) -> _Metric:
    return _Metric(key, _as_float(report.get(key)), minimum)


def _check_scanner(report: dict[str, object], bar: GateThresholds, notes: _Notes) -> None:
    profiles = report.get(_SCANNER_KEY) or []
    scored = [p for p in profiles if p != _NOT_SCORED] if isinstance(profiles, list) else []
    if not scored:
        notes.warnings.append(f"{_SCANNER_KEY}: not scored (optional scanner absent) — skipped")
        return
    metric = _Metric(_SCANNER_KEY, float(len(scored)), float(bar.min_scanner_profiles))
    _record_shortfall(metric, notes.failures)


def _unsupported_axes(report: dict[str, object]) -> list[str]:
    raw = report.get("unsupported_axes") or {}
    families = report.get("families") or []
    if not isinstance(raw, dict):
        return []
    names = list(families) if isinstance(families, list) and families else list(raw)
    if names and all(_PATH_LENGTH in (raw.get(family) or []) for family in names):
        return [_PATH_LENGTH]
    return []


def _as_float(value: object) -> float:
    if isinstance(value, int | float):
        return float(value)
    return 0.0


__all__ = ["GateResult", "GateThresholds", "cosmetic_message", "evaluate_gate"]
