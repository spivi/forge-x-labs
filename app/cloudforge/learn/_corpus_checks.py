"""Per-pattern corpus-validation checks (design §9.5).

Split out of ``corpus.py`` to keep that module under the 200-line cap (rules/general.md).
Each ``_*_issues`` function inspects one ``RiskPattern`` and returns zero or more
``CorpusIssue``s; ``pattern_issues`` runs all of them. Fragment validation is delegated
entirely to ``validate.validate_fragment`` — never reinvented here.
"""

from __future__ import annotations

from enum import StrEnum

from app.cloudforge.learn.pattern_enums import TRAINABLE_CLASSIFICATIONS, SafetyClassification
from app.cloudforge.learn.pattern_models import RiskPattern
from app.cloudforge.learn.source_models import NON_TRAINING_REUSE
from app.cloudforge.learn.validate import validate_fragment, validation_reasons

CorpusIssueTuple = tuple[str, str, str]  # (pattern_id, check, message)

_TRAINABLE_VALUES: frozenset[str] = frozenset(c.value for c in TRAINABLE_CLASSIFICATIONS)
_NON_TRAINING_REUSE_VALUES: frozenset[str] = frozenset(r.value for r in NON_TRAINING_REUSE)


def pattern_issues(pattern: RiskPattern) -> list[CorpusIssueTuple]:
    """Run every single-pattern design §9.5 check against ``pattern``."""
    issues: list[CorpusIssueTuple] = []
    issues.extend(_provenance_issues(pattern))
    issues.extend(_fragment_issues(pattern))
    issues.extend(_unsafe_operational_issues(pattern))
    issues.extend(_training_eligible_consistency_issues(pattern))
    return issues


def _provenance_issues(pattern: RiskPattern) -> list[CorpusIssueTuple]:
    """No provenance, no corpus: every provenance string field must be non-blank."""
    provenance = pattern.provenance
    blank = [
        field
        for field, value in provenance.model_dump(mode="json").items()
        if isinstance(value, str) and field != "notes" and not value.strip()
    ]
    if not blank:
        return []
    message = f"incomplete provenance: blank field(s) {blank}"
    return [(pattern.id, "provenance_complete", message)]


def _fragment_issues(pattern: RiskPattern) -> list[CorpusIssueTuple]:
    """Reuse ``validate.validate_fragment`` — never reinvent fragment validation here."""
    reasons = validation_reasons(pattern)
    validated = validate_fragment(pattern)
    if validated.validation_status.value == "valid" and not reasons:
        return []
    detail = "; ".join(reasons) if reasons else "fragment failed validation"
    return [(pattern.id, "fragment_valid", detail)]


def _unsafe_operational_issues(pattern: RiskPattern) -> list[CorpusIssueTuple]:
    """No ``unsafe_operational`` pattern may be present (must be rejected upstream)."""
    if pattern.safety_classification is not SafetyClassification.UNSAFE_OPERATIONAL:
        return []
    message = "safety_classification is unsafe_operational; must be rejected upstream"
    return [(pattern.id, "no_unsafe_operational", message)]


def _value_of(member: object) -> str:
    """Return a ``StrEnum`` member's ``.value``, or the raw string as-is.

    Defensive against a pattern reaching the corpus through a bypassed validator (e.g.
    ``model_construct``), where an enum-typed field may hold a plain ``str`` instead of
    the enum member — comparing on the underlying value, not identity, keeps the
    eligibility recomputation correct either way.
    """
    return member.value if isinstance(member, StrEnum) else str(member)


def _recompute_training_eligible(pattern: RiskPattern) -> bool:
    """Recompute the design §6 eligibility rule from ``pattern``'s own fields.

    Mirrors ``RiskPattern.training_eligible`` exactly, but compares field *values*
    rather than enum identity so a bypassed-validator pattern (plain strings instead of
    enum members) is still evaluated correctly.
    """
    provenance = pattern.provenance
    return (
        _value_of(pattern.validation_status) == "valid"
        and _value_of(pattern.safety_classification) in _TRAINABLE_VALUES
        and provenance.allowed_for_training
        and _value_of(provenance.reuse_status) not in _NON_TRAINING_REUSE_VALUES
    )


def _training_eligible_consistency_issues(pattern: RiskPattern) -> list[CorpusIssueTuple]:
    """``training_eligible`` must match the documented eligibility rule (design §6/§9.5).

    ``training_eligible`` is a ``computed_field`` derived from ``validation_status``,
    ``safety_classification``, and ``provenance`` — never free-form. A normal
    ``RiskPattern`` built via ``model_validate``/its constructor can never disagree with
    its own computed property. But a pattern reaching the corpus through a bypassed
    validator (e.g. ``model_construct``) can end up with a stored
    ``validation_status``/``safety_classification`` that no longer compares equal to the
    enum members the eligibility rule checks against — silently flipping
    ``training_eligible`` without the pattern *looking* wrong. This check recomputes
    eligibility independently and flags any mismatch as a stored inconsistency.
    """
    expected = _recompute_training_eligible(pattern)
    if pattern.training_eligible == expected:
        return []
    message = (
        f"training_eligible={pattern.training_eligible} does not match the eligibility "
        f"rule applied to its own stored fields (expected={expected}): "
        f"validation_status={pattern.validation_status!r}, "
        f"safety_classification={pattern.safety_classification!r}, "
        f"provenance.allowed_for_training={pattern.provenance.allowed_for_training}, "
        f"provenance.reuse_status={pattern.provenance.reuse_status!r}"
    )
    return [(pattern.id, "training_eligible_consistent", message)]
