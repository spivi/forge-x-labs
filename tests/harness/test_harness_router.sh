#!/usr/bin/env bash
# tests/harness/test_harness_router.sh
# Integration tests for scripts/harness_router.sh.
# Run: bash tests/harness/test_harness_router.sh
# Uses a stubbed `gemini` on PATH — no live Gemini CLI required.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ROUTER="$REPO_ROOT/scripts/harness_router.sh"
PASS=0; FAIL=0
TMPDIR_T="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_T"' EXIT

_pass() { echo "  PASS: $1"; (( PASS++ )) || true; }
_fail() { echo "  FAIL: $1"; (( FAIL++ )) || true; }

_is_json() { echo "$1" | python3 -c "import sys,json; json.load(sys.stdin)" 2>/dev/null; }

# Build a fake `gemini` on a private bin dir. $GEMINI_STUB_OUT controls what it prints.
STUB_BIN="$TMPDIR_T/bin"
mkdir -p "$STUB_BIN"
cat > "$STUB_BIN/gemini" <<'STUB'
#!/usr/bin/env bash
# Ignore all args; echo the configured payload (or a default valid CI JSON).
cat <<<"${GEMINI_STUB_OUT:-{\"status\":\"pass\",\"failed_tests\":[],\"lint_errors\":[],\"type_errors\":[],\"summary_line\":\"ok\"}}"
STUB
chmod +x "$STUB_BIN/gemini"

echo "=== harness_router.sh tests ==="

# T1: missing operation exits non-zero
if bash "$ROUTER" 2>/dev/null; then
    _fail "T1: should exit non-zero with no operation"
else
    _pass "T1: no-op exits non-zero"
fi

# T2: unknown operation exits non-zero
if echo "" | bash "$ROUTER" "unknown-op" 2>/dev/null; then
    _fail "T2: should exit non-zero for unknown operation"
else
    _pass "T2: unknown op exits non-zero"
fi

# T3: security-surface guard forces exit 2 for review-prepass (default glob matches `auth`)
SECURITY_DIFF="diff --git a/app/core/auth.py b/app/core/auth.py
--- a/app/core/auth.py
+++ b/app/core/auth.py
@@ -1,2 +1,3 @@
+# auth change"
if echo "$SECURITY_DIFF" | TICKET="test" HARNESS_ROUTER_LEDGER="$TMPDIR_T/hr.csv" \
    PATH="$STUB_BIN:$PATH" bash "$ROUTER" "review-prepass" 2>/dev/null; then
    _fail "T3: security surface should exit 2 (got 0)"
else
    _pass "T3: security surface guard exits non-zero even with gemini present"
fi

# T4: ledger file is created with the correct header when a provider call is made
# (the security-guard path always logs, even without gemini — a deterministic write).
TMP_LEDGER="$TMPDIR_T/ledger.csv"
echo "diff --git a/app/core/auth.py b/app/core/auth.py" | TICKET="t4" \
    HARNESS_ROUTER_LEDGER="$TMP_LEDGER" PATH="/usr/bin:/bin" \
    bash "$ROUTER" "review-prepass" 2>/dev/null || true
if [[ -f "$TMP_LEDGER" ]] && head -1 "$TMP_LEDGER" | grep -q "ts_iso"; then
    _pass "T4: ledger created with correct header"
else
    _fail "T4: ledger header missing or file not created"
fi

# T5: fallback (exit 2) when gemini is not in PATH
RESULT=0
echo "test ci output" | PATH="/usr/bin:/bin" HARNESS_ROUTER_LEDGER="$TMPDIR_T/hr5.csv" \
    bash "$ROUTER" "summarize-ci" 2>/dev/null || RESULT=$?
if [[ "$RESULT" -eq 2 ]]; then
    _pass "T5: fallback exits 2 when gemini not in PATH"
else
    _fail "T5: expected exit 2, got $RESULT"
fi

# T6: stubbed gemini returning valid JSON → exit 0 + JSON on stdout + ledger row
OUT="$TMPDIR_T/t6.out"; RC=0
echo "PASSED 1 test" | TICKET="t6" HARNESS_ROUTER_LEDGER="$TMPDIR_T/hr6.csv" \
    PATH="$STUB_BIN:/usr/bin:/bin" bash "$ROUTER" "summarize-ci" > "$OUT" 2>/dev/null || RC=$?
if [[ "$RC" -eq 0 ]] && _is_json "$(cat "$OUT")"; then
    _pass "T6: stubbed gemini valid JSON → exit 0 with JSON output"
else
    _fail "T6: expected exit 0 + JSON, got rc=$RC out=$(cat "$OUT")"
fi
if grep -q "summarize-ci,gemini" "$TMPDIR_T/hr6.csv" 2>/dev/null; then
    _pass "T6b: benchmark row written with provider=gemini"
else
    _fail "T6b: gemini ledger row not found"
fi

# T7: stubbed gemini returning NON-JSON → fallback exit 2 (caller uses raw input)
RC=0
echo "ci output" | GEMINI_STUB_OUT="this is not json" TICKET="t7" \
    HARNESS_ROUTER_LEDGER="$TMPDIR_T/hr7.csv" PATH="$STUB_BIN:/usr/bin:/bin" \
    bash "$ROUTER" "summarize-ci" >/dev/null 2>&1 || RC=$?
if [[ "$RC" -eq 2 ]]; then
    _pass "T7: non-JSON gemini output → fallback exit 2"
else
    _fail "T7: expected exit 2 on non-JSON, got $RC"
fi

echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ $FAIL -eq 0 ]]
