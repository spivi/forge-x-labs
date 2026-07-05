#!/usr/bin/env bash
# tests/hooks/test_check_signoff.sh
# Tests for scripts/check-signoff.sh (commit-msg hook).
# Run: bash tests/hooks/test_check_signoff.sh

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
HOOK="$REPO_ROOT/scripts/check-signoff.sh"
PASS=0; FAIL=0
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

_pass() { echo "  PASS: $1"; (( PASS++ )) || true; }
_fail() { echo "  FAIL: $1"; (( FAIL++ )) || true; }

_msg() { printf '%s\n' "$1" > "$TMP/msg"; echo "$TMP/msg"; }

echo "=== check-signoff.sh tests ==="

# T1: missing trailer → exit 1
if SIGNOFF_EMAIL="dev@example.com" bash "$HOOK" "$(_msg "feat: a change")" 2>/dev/null; then
    _fail "T1: missing trailer should exit non-zero"
else
    _pass "T1: missing trailer exits non-zero"
fi

# T2: correct trailer matching required signer → exit 0
M="$(_msg "feat: a change

Signed-off-by: Dev <dev@example.com>")"
if SIGNOFF_EMAIL="dev@example.com" bash "$HOOK" "$M" 2>/dev/null; then
    _pass "T2: matching signer passes"
else
    _fail "T2: matching signer should pass"
fi

# T3: trailer present but wrong email → exit 1
M="$(_msg "feat: a change

Signed-off-by: Someone <other@example.com>")"
if SIGNOFF_EMAIL="dev@example.com" bash "$HOOK" "$M" 2>/dev/null; then
    _fail "T3: wrong signer should exit non-zero"
else
    _pass "T3: wrong signer exits non-zero"
fi

# T4: no required signer resolvable anywhere → any well-formed trailer accepted.
# Neutralize the git-config fallback (empty global/system config) and run outside any
# repo (cd to TMP, no .dev-context/project.conf) so SIGNOFF_EMAIL truly resolves empty.
M="$(_msg "feat: a change

Signed-off-by: Anyone <anyone@example.com>")"
if ( cd "$TMP" && SIGNOFF_EMAIL="" GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
        bash "$HOOK" "$M" 2>/dev/null ); then
    _pass "T4: well-formed trailer accepted when no signer required"
else
    _fail "T4: should accept any well-formed trailer with no required signer"
fi

echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ $FAIL -eq 0 ]]
