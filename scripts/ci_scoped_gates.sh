#!/usr/bin/env bash
# Diff-scoped CI gates — run heavy checks ONLY when the changed paths warrant them,
# so the common path (unrelated work) stays fast.
#
# This is a portable SCAFFOLD: the `touches()` helper + one illustrative gate. Add
# project-specific scoped gates by copying the pattern (detect a path class in the
# diff, run the matching check). Gated by CI_SCOPED_GATES in project.conf (opt-in).
#
# -e so a gate command failure aborts (and fails the scoped-gate run) rather than
# being masked by trailing echoes.
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
CONF="$ROOT/.dev-context/project.conf"

_conf_value() {
    [ -f "$CONF" ] || return 0
    sed -n "s/^$1=//p" "$CONF" 2>/dev/null | head -n1 | sed 's/[[:space:]]*#.*$//; s/^"//; s/"$//'
}

# Opt-in gate (default off — it can run slow/heavy project-specific checks).
[ "$(_conf_value CI_SCOPED_GATES)" = "on" ] || { echo "ci-scoped-gates: CI_SCOPED_GATES!=on — skipping."; exit 0; }

BASE="origin/master"
if ! git fetch --no-tags --quiet origin master 2>/dev/null; then
  echo "WARNING: 'git fetch origin master' failed — gates compare against possibly-stale local ${BASE}." >&2
fi
CHANGED="$(git diff --name-only "${BASE}...HEAD" 2>/dev/null || true)"

touches() { printf '%s\n' "$CHANGED" | grep -Eq "$1"; }

# --- Illustrative scoped gate: UI changes ------------------------------------
# When the diff touches frontend surfaces, remind the author that the (advisory)
# vis-UI screenshot gate (scripts/app_screenshot.py, DT-6) should run pre-merge.
# This is a REMINDER, not an inline run: app_screenshot needs a live app + Playwright
# (opt-in via VIS_UI_GATE), so it cannot run headless here.
if touches '(^|/)(app/templates/|app/static/)|\.(html|css|jsx?|tsx?)$'; then
  echo ">> ci-scoped-gates: UI change detected."
  echo "   Reminder: run the vis-UI screenshot gate before merge when VIS_UI_GATE=on"
  echo "   (python scripts/app_screenshot.py ... — see /sprint merge step 3.6)."
fi

# --- Add project-specific scoped gates below, following the touches() pattern --
# Example:
#   if touches '(^|/)migrations/'; then
#     echo ">> ci-scoped-gates: migration change — running migration smoke."
#     <your migration check>
#   fi

echo "ci-scoped-gates: done."
