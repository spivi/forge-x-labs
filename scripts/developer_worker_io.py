"""Developer Worker I/O: validation parsing + data models.

Data models: ValidationResult, CommitMessage, PRDescription, FailureEscalation.
Functions: parse_ruff_output, parse_mypy_output, parse_pytest_output,
parse_precommit_output, all_validations_pass.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ValidationResult:
    """Output of running lint/test/type-check commands."""

    tool: str
    passed: bool
    output: str
    error_count: int
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CommitMessage:
    """Conventional commit message components."""

    type: str
    scope: str
    subject: str
    body: str = ""
    breaking: bool = False


@dataclass(frozen=True)
class PRDescription:
    """Pull request structured description."""

    title: str
    summary: list[str] = field(default_factory=list)
    ticket_id: str = ""
    test_plan: list[str] = field(default_factory=list)
    files_changed: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FailureEscalation:
    """When developer can't resolve after max attempts."""

    failure_type: str
    attempts: int
    last_error: str
    recommendation: str


# -- Validation Parsers (Phase 5) -------------------------------------------

_RUFF_ERROR_RE = re.compile(r"Found (\d+) error")
_RUFF_LINE_RE = re.compile(r"^.+:\d+:\d+: [A-Z]\d+")


def parse_ruff_output(output: str) -> ValidationResult:
    """Parse ruff check output into ValidationResult."""
    if not output.strip() or "All checks passed" in output:
        return ValidationResult(tool="ruff", passed=True, output=output, error_count=0)
    m = _RUFF_ERROR_RE.search(output)
    count = int(m.group(1)) if m else 0
    errors = [ln.strip() for ln in output.splitlines() if _RUFF_LINE_RE.match(ln.strip())]
    return ValidationResult(
        tool="ruff",
        passed=count == 0,
        output=output,
        error_count=count,
        errors=errors,
    )


_MYPY_FOUND_RE = re.compile(r"Found (\d+) error")


def parse_mypy_output(output: str) -> ValidationResult:
    """Parse mypy output into ValidationResult."""
    if "Success: no issues found" in output:
        return ValidationResult(tool="mypy", passed=True, output=output, error_count=0)
    m = _MYPY_FOUND_RE.search(output)
    count = int(m.group(1)) if m else 0
    errors = [ln.strip() for ln in output.splitlines() if ": error:" in ln]
    return ValidationResult(
        tool="mypy",
        passed=count == 0,
        output=output,
        error_count=count,
        errors=errors,
    )


_PYTEST_PASSED_RE = re.compile(r"(\d+) passed")
_PYTEST_FAILED_RE = re.compile(r"(\d+) failed")
_PYTEST_ERROR_RE = re.compile(r"(\d+) error")


def parse_pytest_output(output: str) -> ValidationResult:
    """Parse pytest output into ValidationResult."""
    if not output.strip():
        return ValidationResult(
            tool="pytest",
            passed=False,
            output=output,
            error_count=0,
            errors=["empty output"],
        )
    failed_m = _PYTEST_FAILED_RE.search(output)
    error_m = _PYTEST_ERROR_RE.search(output)
    fail_count = int(failed_m.group(1)) if failed_m else 0
    err_count = int(error_m.group(1)) if error_m else 0
    total_errors = fail_count + err_count
    passed = total_errors == 0 and bool(_PYTEST_PASSED_RE.search(output))
    return ValidationResult(
        tool="pytest",
        passed=passed,
        output=output,
        error_count=total_errors,
    )


def parse_precommit_output(output: str) -> ValidationResult:
    """Parse pre-commit run output into ValidationResult."""
    failed_hooks = [ln.strip() for ln in output.splitlines() if "Failed" in ln]
    count = len(failed_hooks)
    return ValidationResult(
        tool="pre-commit",
        passed=count == 0,
        output=output,
        error_count=count,
        errors=failed_hooks,
    )


def all_validations_pass(results: list[ValidationResult]) -> bool:
    """Return True if all validation results passed."""
    return all(r.passed for r in results)
