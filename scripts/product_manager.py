"""Product Manager agent — pure functions for idea intake + feasibility.

Data models: IdeaIntake, AffectedModule, FeasibilityReport, RoadmapFinding.
Functions: parse_idea, check_decision_conflict, classify_complexity,
assess_feasibility, parse_todo_findings, prioritize_findings.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

STOP_WORDS = frozenset(
    [
        "the",
        "and",
        "for",
        "with",
        "from",
        "that",
        "this",
        "have",
        "will",
        "when",
        "what",
        "which",
        "their",
        "they",
        "been",
        "more",
        "into",
        "each",
        "also",
        "both",
        "than",
        "very",
        "should",
        "could",
        "would",
        "about",
        "after",
        "before",
        "between",
        "under",
        "over",
        "some",
        "need",
    ]
)

BUGFIX_WORDS = frozenset({"fix", "bug", "broken", "crash", "error", "fault"})
IMPROVEMENT_WORDS = frozenset({"improve", "enhance", "better", "optimize", "refine"})
INFRA_WORDS = frozenset(
    {
        "infra",
        "deploy",
        "cache",
        "migrate",
        "redis",
        "database",
        "ci",
        "docker",
        "kubernetes",
        "pipeline",
        "scale",
        "scaling",
        "multi-tenant",
        "isolation",
        "schema",
        "performance",
    }
)
DEVELOPER_WORDS = frozenset({"developer", "code", "test", "refactor", "lint"})
OPERATOR_WORDS = frozenset({"deploy", "infra", "ci", "monitor", "alert", "ops"})


@dataclass(frozen=True)
class IdeaIntake:
    """Parsed feature idea with classification."""

    raw_text: str
    problem: str
    beneficiary: str  # "user" | "developer" | "operator"
    idea_type: str  # "feature" | "improvement" | "bugfix" | "infrastructure"
    conflicts_with: str  # decision ID or "" if none


@dataclass(frozen=True)
class AffectedModule:
    """A module affected by a proposed feature."""

    file_path: str
    change_type: str  # "modify" | "create" | "extend"
    reason: str


@dataclass(frozen=True)
class FeasibilityReport:
    """Codebase feasibility assessment for a feature idea."""

    idea: IdeaIntake
    affected_modules: list[AffectedModule]
    complexity: str  # "S" | "M" | "L"
    has_existing_pattern: bool
    needs_new_abstraction: bool
    risks: list[str]
    test_surface: str


@dataclass(frozen=True)
class RoadmapFinding:
    """One codebase improvement opportunity."""

    description: str
    finding_type: str  # "todo" | "missing_tests" | "stale_code" | "error_handling"
    priority: str  # "P0" | "P1" | "P2" | "P3"
    file_path: str
    line_number: int
    suggested_action: str


def _classify_beneficiary(words: set[str]) -> str:
    if words & OPERATOR_WORDS:
        return "operator"
    if words & DEVELOPER_WORDS:
        return "developer"
    return "user"


def _classify_type(words: set[str]) -> str:
    if words & BUGFIX_WORDS:
        return "bugfix"
    if words & IMPROVEMENT_WORDS:
        return "improvement"
    if words & INFRA_WORDS:
        return "infrastructure"
    return "feature"


def _extract_problem(raw: str) -> str:
    lower = raw.lower()
    if lower.startswith("problem:"):
        return raw[len("problem:") :].strip().split(".")[0].strip()
    # First clause (before -- or .) as problem summary
    for sep in (" -- ", ". ", " - "):
        if sep in raw:
            return raw.split(sep)[0].strip()
    return raw.strip()


def parse_idea(raw_text: str) -> IdeaIntake:
    """Parse free-text idea into structured IdeaIntake."""
    text = raw_text.strip()
    words = {w.lower().strip(".,;:!?\"'") for w in text.split()}
    return IdeaIntake(
        raw_text=text,
        problem=_extract_problem(text),
        beneficiary=_classify_beneficiary(words),
        idea_type=_classify_type(words),
        conflicts_with="",
    )


def _significant_words(text: str) -> set[str]:
    words = {w.lower().strip(".,;:!?\"'*#") for w in text.split()}
    return {w for w in words if len(w) > 4 and w not in STOP_WORDS}


def _parse_decision_blocks(decisions_text: str) -> list[tuple[str, str, str]]:
    """Return list of (decision_id, status, body_text)."""
    blocks: list[tuple[str, str, str]] = []
    parts = re.split(r"^---\s*$", decisions_text, flags=re.MULTILINE)
    for part in parts:
        id_match = re.search(r"##\s+({{PROJECT_ID}}-D\d+):", part)
        status_match = re.search(r"\*\*Status\*\*:\s*(\S+)", part)
        if id_match and status_match:
            blocks.append((id_match.group(1), status_match.group(1), part))
    return blocks


def check_decision_conflict(idea: IdeaIntake, decisions_text: str) -> IdeaIntake:
    """Check idea against accepted decisions for keyword overlap."""
    if not decisions_text.strip():
        return idea
    idea_words = _significant_words(idea.raw_text)
    for dec_id, status, body in _parse_decision_blocks(decisions_text):
        if "superseded" in status.lower() or "deprecated" in status.lower():
            continue
        dec_words = _significant_words(body)
        overlap = idea_words & dec_words
        if len(overlap) >= 2:
            return IdeaIntake(
                raw_text=idea.raw_text,
                problem=idea.problem,
                beneficiary=idea.beneficiary,
                idea_type=idea.idea_type,
                conflicts_with=dec_id,
            )
    return idea


def classify_complexity(affected_count: int) -> str:
    """Map affected module count to S/M/L complexity."""
    if affected_count <= 2:
        return "S"
    if affected_count <= 5:
        return "M"
    return "L"


def assess_feasibility(
    idea: IdeaIntake, codebase_modules: list[AffectedModule]
) -> FeasibilityReport:
    """Build feasibility report from idea + affected modules."""
    complexity = classify_complexity(len(codebase_modules))
    change_types = {m.change_type for m in codebase_modules}
    has_existing = bool(change_types & {"modify", "extend"})
    needs_abstraction = "create" in change_types and complexity in ("M", "L")
    risks: list[str] = []
    if needs_abstraction:
        risks.append("New abstraction required — design review recommended")
    if complexity == "L":
        risks.append("High complexity — consider phased rollout")
    test_surface = f"{len(codebase_modules)} modules affected — integration tests needed"
    return FeasibilityReport(
        idea=idea,
        affected_modules=codebase_modules,
        complexity=complexity,
        has_existing_pattern=has_existing,
        needs_new_abstraction=needs_abstraction,
        risks=risks,
        test_surface=test_surface,
    )


_LINE_RE = re.compile(r"^(.+?):(\d+):(.*)$")
_P1_KEYWORDS = frozenset({"FIXME", "HACK", "XXX"})


def _classify_finding(text: str) -> tuple[str, str]:
    upper = text.upper()
    for kw in _P1_KEYWORDS:
        if kw in upper:
            ftype = "error_handling" if kw == "FIXME" else "stale_code"
            return "P1", ftype
    if "TODO" in upper:
        return "P2", "todo"
    return "P3", "missing_feature"


def parse_todo_findings(grep_output: str) -> list[RoadmapFinding]:
    """Parse grep-style file:line:text into RoadmapFindings."""
    findings: list[RoadmapFinding] = []
    for line in grep_output.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        match = _LINE_RE.match(line)
        if not match:
            continue
        path, lineno, text = match.group(1), int(match.group(2)), match.group(3)
        priority, ftype = _classify_finding(text)
        findings.append(
            RoadmapFinding(
                description=text.strip().lstrip("#").strip(),
                finding_type=ftype,
                priority=priority,
                file_path=path,
                line_number=lineno,
                suggested_action=f"Address {ftype} in {path}:{lineno}",
            )
        )
    return findings


_PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


def prioritize_findings(findings: list[RoadmapFinding]) -> list[RoadmapFinding]:
    """Sort findings by priority (P0 first), then file path."""
    return sorted(
        findings,
        key=lambda f: (_PRIORITY_ORDER.get(f.priority, 9), f.file_path),
    )
