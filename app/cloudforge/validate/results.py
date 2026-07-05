"""Validation outcome types.

An outcome is PASS, WARN (e.g. an optional tool is missing — never fatal), or FAIL
(a real validation failure). The report knows if any FAIL occurred so the CLI can
choose its exit code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Status(StrEnum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


@dataclass(frozen=True)
class ValidationOutcome:
    """One check's result: a status, a short label, and an optional detail."""

    status: Status
    label: str
    detail: str = ""

    def render(self) -> str:
        suffix = f" {self.detail}" if self.detail else ""
        return f"[{self.status.value}] {self.label}.{suffix}".rstrip()


@dataclass
class ValidationReport:
    """Accumulated outcomes across the whole validation run."""

    outcomes: list[ValidationOutcome] = field(default_factory=list)

    def add(self, outcome: ValidationOutcome) -> None:
        self.outcomes.append(outcome)

    def extend(self, outcomes: list[ValidationOutcome]) -> None:
        self.outcomes.extend(outcomes)

    @property
    def has_failure(self) -> bool:
        return any(o.status is Status.FAIL for o in self.outcomes)
