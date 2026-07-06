"""``opa test`` wrapper for the Rego unit-test suite (FXL-STRESS-6).

``policies/scenario_test.rego`` holds native ``opa test`` cases (``test_`` rules,
discovered by ``opa test``) that pin down every ``deny`` rule in
``policies/scenario.rego`` in isolation — the happy path, each forbidden-permission
pattern, the resource budget, the family-agnostic critical-path/sensitive-sink
gate, and the no-real-secrets attribute scan. This module runs that suite via the
real ``opa`` binary and asserts (a) it passes and (b) coverage of the policy file
meets the bar — mirroring how ``test_opa_policy.py`` gates its real-graph ``opa
eval`` tests on tool presence (S13: optional tools fail-soft only when absent, never
hard-required in the fast suite).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

_POLICIES_DIR = Path("policies")
_POLICY_FILE = "policies/scenario.rego"
_MIN_COVERAGE_PCT = 85.0

_opa_required = pytest.mark.skipif(
    shutil.which("opa") is None,
    reason="opa binary not installed — skipping opa test suite (fail-soft, S13)",
)


def _run_opa_test(*extra_args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 — fixed argv, no shell, opa from PATH
        ["opa", "test", str(_POLICIES_DIR), *extra_args],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )


@_opa_required
def test_opa_policy_suite_passes() -> None:
    """``opa test policies/`` — every ``test_`` rule in ``scenario_test.rego`` passes."""
    result = _run_opa_test("-v")

    assert result.returncode == 0, result.stdout + result.stderr


@_opa_required
def test_opa_policy_coverage_meets_bar() -> None:
    """``opa test policies/ --coverage`` — ``scenario.rego`` line coverage >= 85%."""
    result = _run_opa_test("--coverage", "--format=json")
    assert result.returncode == 0, result.stdout + result.stderr

    payload: dict[str, Any] = json.loads(result.stdout)
    file_coverage = payload["files"][_POLICY_FILE]
    policy_coverage = file_coverage["coverage"]
    gaps = json.dumps(file_coverage.get("not_covered", []))

    assert policy_coverage >= _MIN_COVERAGE_PCT, (
        f"{_POLICY_FILE} coverage {policy_coverage:.2f}% is below the "
        f"{_MIN_COVERAGE_PCT}% bar — uncovered: {gaps}"
    )
