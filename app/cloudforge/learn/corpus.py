"""Corpus load/save + corpus-level validation gate (design §9.5).

Mirrors the 12-point scenario discipline, applied to the whole corpus rather
than a single pattern: every pattern has complete provenance (**no provenance, no
corpus**), every ``graph_fragment`` passes fragment validation (reusing
``validate.validate_fragment`` — never reinvented; see ``_corpus_checks.py``), no two
patterns share an ``id``, no ``unsafe_operational`` pattern is present,
``safety_classification`` / ``training_eligible`` stay internally consistent with
provenance, and every enum value is in-vocabulary (Pydantic enforces this at load; see
``load_corpus``).

``load_corpus``/``save_corpus`` round-trip a corpus as JSONL (one ``RiskPattern``
``model_dump`` per line) — deterministic and lossless.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError

from app.cloudforge.errors import CloudforgeError
from app.cloudforge.learn._corpus_checks import pattern_issues
from app.cloudforge.learn.pattern_models import RiskPattern

_TRAINING_ELIGIBLE_KEY = "training_eligible"


class CorpusLoadError(CloudforgeError):
    """A corpus JSONL file is missing, unreadable, or has a malformed line."""


class CorpusIssue(BaseModel):
    """One corpus-validation violation (design §9.5)."""

    model_config = ConfigDict(extra="forbid")

    pattern_id: str
    check: str
    message: str


class CorpusValidationReport(BaseModel):
    """Outcome of :func:`validate_corpus`: pass/fail plus itemized issues."""

    model_config = ConfigDict(extra="forbid")

    pattern_count: int
    issues: list[CorpusIssue]

    @property
    def passed(self) -> bool:
        """``True`` iff no pattern raised any issue."""
        return not self.issues


# --- load / save ---------------------------------------------------------------------


def load_corpus(path: Path) -> list[RiskPattern]:
    """Read a JSONL corpus file into ``RiskPattern`` models.

    Enums are validated in-vocabulary by Pydantic itself: any field holding a value
    outside its ``StrEnum`` fails ``model_validate`` and surfaces as a clear
    ``CorpusLoadError`` below, rather than a silently-accepted unknown value.

    ``training_eligible`` is a ``computed_field`` on ``RiskPattern`` (derived, not
    settable), so the stored value from a prior ``save_corpus`` is popped off the
    payload before construction (``model_validate`` would otherwise reject it as an
    unknown field).

    Raises ``CorpusLoadError`` (a ``CloudforgeError``) if the file is missing/unreadable
    or any non-blank line fails JSON decoding or ``RiskPattern`` validation. Blank lines
    are skipped.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CorpusLoadError(f"cannot read corpus {path}: {exc}") from exc

    patterns: list[RiskPattern] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        patterns.append(_parse_line(line, path, line_no))
    return patterns


def _parse_line(line: str, path: Path, line_no: int) -> RiskPattern:
    try:
        payload = json.loads(line)
    except json.JSONDecodeError as exc:
        raise CorpusLoadError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise CorpusLoadError(f"{path}:{line_no}: expected a JSON object")
    payload = dict(payload)
    payload.pop(_TRAINING_ELIGIBLE_KEY, None)
    try:
        return RiskPattern.model_validate(payload)
    except ValidationError as exc:
        raise CorpusLoadError(f"{path}:{line_no}: invalid RiskPattern: {exc}") from exc


def save_corpus(patterns: list[RiskPattern], path: Path) -> None:
    """Write ``patterns`` as JSONL, one ``model_dump`` per line, in the given order.

    Deterministic: identical input always produces identical bytes (stable field order
    from ``model_dump``, no set/dict iteration on the output side). Lossless: every
    settable field round-trips through ``load_corpus`` unchanged; ``training_eligible``
    (computed, not settable) is recomputed identically on load from those same fields.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(p.model_dump(mode="json"), sort_keys=True) for p in patterns]
    text = "".join(f"{line}\n" for line in lines)
    path.write_text(text, encoding="utf-8")


# --- corpus-level validation -----------------------------------------------------------


def validate_corpus(patterns: list[RiskPattern]) -> CorpusValidationReport:
    """Run every design §9.5 corpus-level check and return an itemized report."""
    issues: list[CorpusIssue] = _duplicate_id_issues(patterns)
    for pattern in patterns:
        issues.extend(
            CorpusIssue(pattern_id=pid, check=check, message=message)
            for pid, check, message in pattern_issues(pattern)
        )
    return CorpusValidationReport(pattern_count=len(patterns), issues=issues)


def _duplicate_id_issues(patterns: list[RiskPattern]) -> list[CorpusIssue]:
    """No two patterns may share an ``id`` (design §9.5)."""
    seen: dict[str, int] = {}
    for pattern in patterns:
        seen[pattern.id] = seen.get(pattern.id, 0) + 1
    dupes = sorted(pid for pid, count in seen.items() if count > 1)
    return [
        CorpusIssue(pattern_id=pid, check="unique_id", message=f"id {pid!r} is not unique")
        for pid in dupes
    ]
