#!/usr/bin/env bash
# tests/hooks/test_recheck_on_push.sh
# Tests for .claude/hooks/recheck-on-push.sh (PostToolUse Bash hook).
# Run: bash tests/hooks/test_recheck_on_push.sh
# Uses a stubbed `gh` on PATH — no live GitHub required. The hook ALWAYS exits 0
# (fail-soft); these tests assert its SIDE EFFECTS (the .review-pending marker).

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
HOOK="$REPO_ROOT/.claude/hooks/recheck-on-push.sh"
PASS=0; FAIL=0
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

_pass() { echo "  PASS: $1"; (( PASS++ )) || true; }
_fail() { echo "  FAIL: $1"; (( FAIL++ )) || true; }

# A fake project root with project.conf (owner/repo set) + .dev-context for the marker.
ROOT="$TMP/proj"; mkdir -p "$ROOT/.dev-context"
cat > "$ROOT/.dev-context/project.conf" <<'CONF'
REVIEW_RECHECK=on
GITHUB_OWNER=acme
GITHUB_REPO=widget
CONF

# Stub gh: pr list → PR 7; pr view → a head SHA; status → pending (not success);
# `gh api -X POST .../statuses/...` → success (no-op).
STUB="$TMP/bin"; mkdir -p "$STUB"
cat > "$STUB/gh" <<'GH'
#!/usr/bin/env bash
case "$*" in
  *"pr list"*)              echo "7" ;;
  *"pr view"*headRefOid*)   echo "deadbeefcafe" ;;
  *"commits/"*"/status"*)   echo "${GH_STATUS:-pending}" ;;
  *"-X POST"*statuses*)     exit 0 ;;
  *) exit 0 ;;
esac
GH
chmod +x "$STUB/gh"
# Stub git so branch resolution returns a real branch (the hook calls git rev-parse).
cat > "$STUB/git" <<'GIT'
#!/usr/bin/env bash
case "$*" in
  *"rev-parse --abbrev-ref HEAD"*) echo "feat/x" ;;
  *"rev-parse --show-toplevel"*)   echo "$FAKE_ROOT" ;;
  *) exit 0 ;;
esac
GIT
chmod +x "$STUB/git"

_payload() { printf '{"tool_input":{"command":"%s"}}' "$1"; }

echo "=== recheck-on-push.sh tests ==="

# T1: non-git command → silent no-op, no marker written
rm -f "$ROOT/.dev-context/.review-pending"
echo "$(_payload "ls -la")" | CLAUDE_PROJECT_DIR="$ROOT" FAKE_ROOT="$ROOT" \
    PATH="$STUB:/usr/bin:/bin" bash "$HOOK" >/dev/null 2>&1
RC=$?
if [[ $RC -eq 0 && ! -f "$ROOT/.dev-context/.review-pending" ]]; then
    _pass "T1: non-git command → no-op, no marker"
else
    _fail "T1: expected no-op + no marker (rc=$RC, marker=$([ -f "$ROOT/.dev-context/.review-pending" ] && echo yes || echo no))"
fi

# T2: git push with pending status → marker written for the new SHA
rm -f "$ROOT/.dev-context/.review-pending"
echo "$(_payload "git push origin feat/x")" | CLAUDE_PROJECT_DIR="$ROOT" FAKE_ROOT="$ROOT" \
    GH_STATUS="pending" PATH="$STUB:/usr/bin:/bin" bash "$HOOK" >/dev/null 2>&1
if [[ -f "$ROOT/.dev-context/.review-pending" ]] && grep -q "deadbeefcafe" "$ROOT/.dev-context/.review-pending"; then
    _pass "T2: git push with pending status writes marker"
else
    _fail "T2: expected .review-pending marker with head SHA"
fi

# T3: idempotent — SHA already success → no marker (short-circuit)
rm -f "$ROOT/.dev-context/.review-pending"
echo "$(_payload "git push origin feat/x")" | CLAUDE_PROJECT_DIR="$ROOT" FAKE_ROOT="$ROOT" \
    GH_STATUS="success" PATH="$STUB:/usr/bin:/bin" bash "$HOOK" >/dev/null 2>&1
if [[ ! -f "$ROOT/.dev-context/.review-pending" ]]; then
    _pass "T3: already-success SHA → no marker (idempotent)"
else
    _fail "T3: should short-circuit when status already success"
fi

# T4: gate off → no-op even on a git push
rm -f "$ROOT/.dev-context/.review-pending"
echo "REVIEW_RECHECK=off" > "$ROOT/.dev-context/project.conf"
echo "$(_payload "git push origin feat/x")" | CLAUDE_PROJECT_DIR="$ROOT" FAKE_ROOT="$ROOT" \
    PATH="$STUB:/usr/bin:/bin" bash "$HOOK" >/dev/null 2>&1
if [[ ! -f "$ROOT/.dev-context/.review-pending" ]]; then
    _pass "T4: REVIEW_RECHECK=off → no-op"
else
    _fail "T4: gate off should not write a marker"
fi

echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ $FAIL -eq 0 ]]
