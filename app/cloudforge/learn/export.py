"""Training-export gate + writer (design §9.6).

A pattern is written to the training export only if ALL hold: ``validation_status ==
valid``, ``training_eligible == true``, ``safety_classification`` in the trainable set,
``provenance.reuse_status`` allows reuse, ``provenance.allowed_for_training == true``,
and ``quality_score >= 0.70``. The first four conditions plus the reuse/training flags
are already encoded by ``RiskPattern.training_eligible`` (the reuse-status rule:
``mappings_only`` is training-eligible; ``restricted``/``metadata_only``/``unknown`` are
not) — this module never re-derives them, it reuses ``training_eligible`` as the single
source of truth and adds only the quality bar.

``--include-restricted`` (design §9.6) locally overrides the ``restricted_source``
reuse exclusion: it admits patterns that would be eligible except for
``reuse_status == restricted`` (still valid, still safe, still >= the quality bar) —
but NEVER admits ``unsafe_operational`` safety. The manifest always records whether the
flag was used and how many patterns it admitted.

The export bundle is a versioned JSONL file (one exported ``RiskPattern``
``model_dump(mode="json")`` per line, deterministic — mirrors ``corpus.py::save_corpus``)
plus a JSON manifest (counts, exclusion breakdown, coverage, the ruleset used). Coverage
counts reuse ``quality.summarize_corpus`` over the admitted records rather than
reinventing aggregation.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.cloudforge.learn.export_models import (
    EXPORT_FORMAT_VERSION,
    EXPORT_RULESET,
    ExclusionBreakdown,
    TrainingExport,
    TrainingExportManifest,
)
from app.cloudforge.learn.pattern_enums import (
    TRAINABLE_CLASSIFICATIONS,
    SafetyClassification,
    ValidationStatus,
)
from app.cloudforge.learn.pattern_models import RiskPattern
from app.cloudforge.learn.quality import EXPORT_QUALITY_BAR, summarize_corpus
from app.cloudforge.learn.source_models import ReuseStatus

CORPUS_FILENAME = "corpus.jsonl"
MANIFEST_FILENAME = "manifest.json"

_UNSAFE = "unsafe_operational"
_RESTRICTED_EXCLUDED = "restricted_source_excluded"
_NOT_ELIGIBLE = "not_training_eligible"
_BELOW_BAR = "below_quality_bar"


def is_exportable(pattern: RiskPattern, *, include_restricted: bool = False) -> tuple[bool, str]:
    """Apply the design §9.6 export gate to one ``pattern``.

    Returns ``(admitted, reason)``: ``reason`` is ``""`` when admitted, otherwise one of
    ``"unsafe_operational"``, ``"restricted_source_excluded"``, ``"not_training_eligible"``,
    or ``"below_quality_bar"``. Never re-derives the reuse/safety/validation checks that
    ``training_eligible`` already encodes — the only extra logic here is the quality bar
    and the explicit, opt-in ``restricted_source`` relaxation.
    """
    if pattern.safety_classification is SafetyClassification.UNSAFE_OPERATIONAL:
        return False, _UNSAFE

    if pattern.training_eligible:
        return _gate_on_quality(pattern)

    if _restricted_but_otherwise_eligible(pattern):
        if not include_restricted:
            return False, _RESTRICTED_EXCLUDED
        return _gate_on_quality(pattern)

    return False, _NOT_ELIGIBLE


def _gate_on_quality(pattern: RiskPattern) -> tuple[bool, str]:
    if pattern.quality_score < EXPORT_QUALITY_BAR:
        return False, _BELOW_BAR
    return True, ""


def _restricted_but_otherwise_eligible(pattern: RiskPattern) -> bool:
    """``True`` iff ``pattern`` fails only the ``reuse_status == restricted`` check.

    Requires everything ``training_eligible`` requires except reuse status: valid,
    safely classified as trainable, and provenance still declares
    ``allowed_for_training``. This is a separate, explicit relaxation — it does not
    weaken ``RiskPattern.training_eligible`` itself.
    """
    return (
        pattern.validation_status is ValidationStatus.VALID
        and pattern.safety_classification in TRAINABLE_CLASSIFICATIONS
        and pattern.provenance.allowed_for_training
        and pattern.provenance.reuse_status is ReuseStatus.RESTRICTED
    )


def export_training(
    patterns: list[RiskPattern], *, include_restricted: bool = False
) -> TrainingExport:
    """Apply the export gate to ``patterns`` and build a pure ``TrainingExport``.

    No I/O. Deterministic: patterns are emitted in their input order (callers that want
    a stable on-disk order should pass already-sorted ``patterns``, e.g. sorted by id).
    """
    admitted: list[RiskPattern] = []
    breakdown = ExclusionBreakdown()
    restricted_admitted_count = 0

    for pattern in patterns:
        ok, reason = is_exportable(pattern, include_restricted=include_restricted)
        if ok:
            admitted.append(pattern)
            if pattern.provenance.reuse_status is ReuseStatus.RESTRICTED:
                restricted_admitted_count += 1
            continue
        _record_exclusion(breakdown, reason)

    coverage = summarize_corpus(admitted)
    manifest = TrainingExportManifest(
        version=EXPORT_FORMAT_VERSION,
        total_input=len(patterns),
        exported_count=len(admitted),
        excluded_count=len(patterns) - len(admitted),
        excluded_breakdown=breakdown,
        provider_coverage=coverage.provider_coverage,
        domain_coverage=coverage.domain_coverage,
        weakness_family_coverage=coverage.weakness_family_coverage,
        quality_bar=EXPORT_QUALITY_BAR,
        ruleset=list(EXPORT_RULESET),
        include_restricted=include_restricted,
        restricted_admitted_count=restricted_admitted_count,
    )
    return TrainingExport(manifest=manifest, records=admitted)


def _record_exclusion(breakdown: ExclusionBreakdown, reason: str) -> None:
    if reason == _UNSAFE:
        breakdown.unsafe_operational += 1
    elif reason == _RESTRICTED_EXCLUDED:
        breakdown.restricted_source_excluded += 1
    elif reason == _BELOW_BAR:
        breakdown.below_quality_bar += 1
    else:
        breakdown.not_training_eligible += 1


def write_training_export(export: TrainingExport, out_dir: Path) -> None:
    """Write ``export`` to ``out_dir`` as ``corpus.jsonl`` + ``manifest.json``.

    Deterministic: identical input always produces identical bytes (stable field order
    from ``model_dump``, sorted JSON keys — mirrors ``corpus.py::save_corpus``).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(p.model_dump(mode="json"), sort_keys=True) for p in export.records]
    corpus_text = "".join(f"{line}\n" for line in lines)
    (out_dir / CORPUS_FILENAME).write_text(corpus_text, encoding="utf-8")

    manifest_json = json.dumps(export.manifest.model_dump(mode="json"), sort_keys=True, indent=2)
    (out_dir / MANIFEST_FILENAME).write_text(f"{manifest_json}\n", encoding="utf-8")
