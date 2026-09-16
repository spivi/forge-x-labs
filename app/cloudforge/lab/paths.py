"""Student/instructor directory contract for one lab output."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

STUDENT_DIR = "student"
INSTRUCTOR_DIR = "instructor"
ESTATE_JSON = "estate.json"
ESTATE_HTML = "estate.html"
BRIEF_MD = "brief.md"
GRADE_KEY = "grade_key.json"
FORBIDDEN_STUDENT_NAMES = frozenset(
    {
        "expected_findings.json",
        "ground_truth_paths.json",
        "report.md",
        "grade_key.json",
        "graph.json",
    }
)


@dataclass(frozen=True)
class LabPaths:
    """Resolved paths under a lab ``--out`` directory."""

    base: Path

    @classmethod
    def from_dir(cls, base: Path | str) -> LabPaths:
        return cls(base=Path(base))

    @property
    def student(self) -> Path:
        return self.base / STUDENT_DIR

    @property
    def instructor(self) -> Path:
        return self.base / INSTRUCTOR_DIR

    @property
    def brief(self) -> Path:
        return self.student / BRIEF_MD

    @property
    def estate_json(self) -> Path:
        return self.student / ESTATE_JSON

    @property
    def estate_html(self) -> Path:
        return self.student / ESTATE_HTML

    @property
    def grade_key(self) -> Path:
        return self.instructor / GRADE_KEY
