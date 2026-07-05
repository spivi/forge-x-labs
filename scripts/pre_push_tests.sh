#!/usr/bin/env bash
# Fast pre-push test backstop (local-CI lane).
#
# A quick safety net for human/agent pushes — NOT the slow, full-suite run.
# Speed comes from four moves:
#   1. skip entirely when no Python/test code changed (e.g. docs-only pushes)
#   2. impacted-only across fix-cycle re-pushes via pytest-testmon (preferred)
#   3. else parallel (-n auto) via pytest-xdist
#   4. always: no coverage, and the e2e/slow markers deselected
# (testmon and xdist are mutually exclusive — never combined. Both are optional;
# without them the hook falls through to a plain fast pytest run.)
# Gated by PRE_PUSH_TESTS in .dev-context/project.conf.
set -uo pipefail

# Respect the project.conf gate (default on; treat unset as on).
CONF="$(git rev-parse --show-toplevel 2>/dev/null)/.dev-context/project.conf"
if [ -f "$CONF" ] && grep -Eq '^PRE_PUSH_TESTS=off' "$CONF"; then
  echo "pre-push: PRE_PUSH_TESTS=off — skipping."
  exit 0
fi

PYTEST="${PYTEST_CMD:-.venv/bin/pytest}"

# --- Resolve the change range ------------------------------------------------
# pre-commit sets PRE_COMMIT_FROM_REF / PRE_COMMIT_TO_REF for the pre-push stage.
# Fall back to the upstream tracking ref, then to origin/master.
FROM="${PRE_COMMIT_FROM_REF:-}"
TO="${PRE_COMMIT_TO_REF:-}"
if [ -z "$FROM" ] || [ -z "$TO" ]; then
  TO="HEAD"
  FROM="$(git rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>/dev/null || echo origin/master)"
fi
# New branch with no remote counterpart → PRE_COMMIT_FROM_REF is all-zeros.
if printf '%s' "$FROM" | grep -Eq '^0+$'; then
  FROM="origin/master"
fi

CHANGED="$(git diff --name-only "$FROM" "$TO" 2>/dev/null || git diff --name-only 'origin/master...HEAD' 2>/dev/null || true)"

# --- 1. Skip when nothing testable changed -----------------------------------
# Testable = package code (app/), the test tree (tests/), standalone Python under
# scripts/, or dependency/build manifests.
if ! printf '%s\n' "$CHANGED" | grep -Eq '(^|/)(app/|tests/|scripts/)|(^|/)pyproject\.toml$'; then
  echo "pre-push: no Python/test changes in ${FROM}..${TO} — skipping pytest."
  exit 0
fi

# --- 2-4. Build the fastest available invocation -----------------------------
# Deselect e2e/slow (heavy) and serial (spawns own processes — would deadlock the
# xdist fallback below).
PYTEST_ARGS=(-q --no-cov -p no:cacheprovider -m "not e2e and not slow and not serial")

if "$PYTEST"  --help 2>/dev/null | grep -q -- '--testmon'; then
  # Impacted-only: persisted .testmondata means a re-push after a small edit
  # runs only the affected tests. Single-process (incompatible with xdist).
  PYTEST_ARGS+=(--testmon)
  echo "pre-push: impacted tests only (testmon), no coverage, e2e/slow deselected…"
elif "$PYTEST" --help 2>/dev/null | grep -q -- '-n '; then
  PYTEST_ARGS+=(-n auto)
  echo "pre-push: fast suite in parallel (-n auto), no coverage, e2e/slow deselected…"
else
  echo "pre-push: fast suite, no coverage, e2e/slow deselected (install pytest-testmon/-xdist to speed up)…"
fi

exec env PYTHONPATH=. "$PYTEST" "${PYTEST_ARGS[@]}" tests/
