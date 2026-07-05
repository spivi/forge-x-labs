#!/usr/bin/env bash
# Tests for .claude/hooks/sync-context.sh
# Validates Gateway Sync session-start hook behavior
#
# Exit 0 = all tests pass, Exit 1 = at least one test failed
#
# NOTE: This is a template. Test data uses generic project identifiers
# (TST for project ID, TST-DNN for decisions). Adapt to your project's
# {{PROJECT_ID}} and {{TICKET_PREFIX}} after template instantiation.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
HOOK_SCRIPT="$PROJECT_DIR/.claude/hooks/sync-context.sh"

# --- Detect project ID from project.conf if available ---
PROJECT_CONF="$PROJECT_DIR/.dev-context/project.conf"
if [[ -f "$PROJECT_CONF" ]]; then
  PROJECT_ID=$(grep -E '^PROJECT_ID=' "$PROJECT_CONF" | cut -d= -f2 | tr -d '"' | tr -d "'") || PROJECT_ID="TST"
else
  PROJECT_ID="TST"
fi

# --- Test tracking ---
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

pass() {
  TESTS_PASSED=$((TESTS_PASSED + 1))
  echo "  PASS: $1"
}

fail() {
  TESTS_FAILED=$((TESTS_FAILED + 1))
  echo "  FAIL: $1"
  echo "    Expected: $2"
  echo "    Got:      $3"
}

# --- Cleanup on exit ---
CLEANUP_DIRS=()
cleanup() {
  for d in "${CLEANUP_DIRS[@]+"${CLEANUP_DIRS[@]}"}"; do
    [[ -d "$d" ]] && rm -rf "$d"
  done
}
trap cleanup EXIT

# Helper: create a temp project dir and register for cleanup
make_test_project() {
  local d
  d=$(mktemp -d)
  CLEANUP_DIRS+=("$d")
  mkdir -p "$d/.dev-context"
  echo "$d"
}

# Helper: standard hook input JSON
hook_input() {
  local session_id="${1:-test}"
  local source="${2:-startup}"
  echo "{\"session_id\":\"${session_id}\",\"source\":\"${source}\",\"cwd\":\".\",\"permission_mode\":\"default\",\"hook_event_name\":\"SessionStart\",\"model\":\"claude-opus-4-6\"}"
}

# ===================================================================
# Test 1: Hook script exists and is executable
# ===================================================================
echo "Test 1: Hook script exists and is executable"
TESTS_RUN=$((TESTS_RUN + 1))
if [[ -x "$HOOK_SCRIPT" ]]; then
  pass "Script exists and is executable"
else
  fail "Script exists and is executable" "executable file at $HOOK_SCRIPT" "not found or not executable"
fi

# ===================================================================
# Test 2: Outputs project status when STATUS.md exists
# ===================================================================
echo "Test 2: Outputs project status when STATUS.md exists"

TEST_DIR=$(make_test_project)
cat > "$TEST_DIR/STATUS.md" << EOF
# Project Status

**Current Phase:** AI Agent Pipeline -- Foundation (${PROJECT_ID}-D012)
**Last Updated:** 2026-02-14

## Recent Achievements
- Layer 1 Cost Governance complete

### Next Steps
1. Merge PRs
2. Execute dry run
EOF

export CLAUDE_PROJECT_DIR="$TEST_DIR"
OUTPUT=$(hook_input "test_status" "startup" | "$HOOK_SCRIPT" 2>/dev/null)

TESTS_RUN=$((TESTS_RUN + 1))
if echo "$OUTPUT" | grep -q "Current Phase"; then
  pass "Output includes current phase from STATUS.md"
else
  fail "Output includes current phase" "contains 'Current Phase'" "output: ${OUTPUT:0:200}"
fi

TESTS_RUN=$((TESTS_RUN + 1))
if echo "$OUTPUT" | grep -q "Next Steps"; then
  pass "Output includes next steps from STATUS.md"
else
  fail "Output includes next steps" "contains 'Next Steps'" "output: ${OUTPUT:0:200}"
fi

# ===================================================================
# Test 3: Outputs top backlog items and decisions
# ===================================================================
echo "Test 3: Outputs top backlog items and decisions"

TEST_DIR=$(make_test_project)
cat > "$TEST_DIR/STATUS.md" << 'EOF'
# Status
**Current Phase:** Testing
**Last Updated:** 2026-02-14
EOF
cat > "$TEST_DIR/BACKLOG.md" << EOF
# Backlog

## Ready

- [ ] **${PROJECT_ID}-037**: Implement Gateway Sync
  - Priority: P1
- [ ] **${PROJECT_ID}-038**: Generate snapshots
  - Priority: P2
- [ ] **${PROJECT_ID}-039**: Write PM spec
  - Priority: P1
EOF
cat > "$TEST_DIR/.dev-context/DECISIONS.md" << EOF
# Decisions

## ${PROJECT_ID}-D001: Use Meta Cloud API
**Status**: accepted
**Decision**: Use Meta Cloud API directly.

## ${PROJECT_ID}-D014: Gateway Sync
**Status**: accepted
**Decision**: Add Gateway Sync agent for multi-surface context.
EOF

export CLAUDE_PROJECT_DIR="$TEST_DIR"
OUTPUT=$(hook_input "test_backlog" "startup" | "$HOOK_SCRIPT" 2>/dev/null)

TESTS_RUN=$((TESTS_RUN + 1))
if echo "$OUTPUT" | grep -q "${PROJECT_ID}-037"; then
  pass "Output includes top backlog ticket ${PROJECT_ID}-037"
else
  fail "Output includes top backlog ticket" "contains ${PROJECT_ID}-037" "output: ${OUTPUT:0:300}"
fi

TESTS_RUN=$((TESTS_RUN + 1))
if echo "$OUTPUT" | grep -q "${PROJECT_ID}-D001\|${PROJECT_ID}-D014"; then
  pass "Output includes recent decisions"
else
  fail "Output includes recent decisions" "contains ${PROJECT_ID}-D001 or ${PROJECT_ID}-D014" "output: ${OUTPUT:0:300}"
fi

# ===================================================================
# Test 4: Outputs inbox summary with counts
# ===================================================================
echo "Test 4: Outputs inbox summary with counts"

TEST_DIR=$(make_test_project)
mkdir -p "$TEST_DIR/.dev-context/inbox/critical"
mkdir -p "$TEST_DIR/.dev-context/inbox/approval"
mkdir -p "$TEST_DIR/.dev-context/inbox/digest"
mkdir -p "$TEST_DIR/.dev-context/inbox/archive"
cat > "$TEST_DIR/STATUS.md" << 'EOF'
# Status
**Current Phase:** Testing
**Last Updated:** 2026-02-14
EOF

cat > "$TEST_DIR/.dev-context/inbox/critical/2026-02-14T10-00-cfo-budget-exceeded.md" << 'EOF'
# Budget Exceeded
**From**: CFO Agent
**Status**: PENDING
EOF
cat > "$TEST_DIR/.dev-context/inbox/approval/2026-02-14T09-00-pm-prd-test.md" << 'EOF'
# PRD: Test Feature
**From**: Product Manager
**Status**: PENDING
EOF
cat > "$TEST_DIR/.dev-context/inbox/digest/2026-02-14T08-00-cfo-report.md" << 'EOF'
# Daily Report
**From**: CFO Agent
**Status**: PENDING
EOF

export CLAUDE_PROJECT_DIR="$TEST_DIR"
OUTPUT=$(hook_input "test_inbox" "startup" | "$HOOK_SCRIPT" 2>/dev/null)

TESTS_RUN=$((TESTS_RUN + 1))
if echo "$OUTPUT" | grep -qi "critical"; then
  pass "Output mentions critical inbox items"
else
  fail "Output mentions critical inbox items" "contains 'critical' mention" "output: ${OUTPUT:0:300}"
fi

TESTS_RUN=$((TESTS_RUN + 1))
if echo "$OUTPUT" | grep -qi "approval\|awaiting"; then
  pass "Output mentions approval inbox items"
else
  fail "Output mentions approval inbox items" "contains 'approval' mention" "output: ${OUTPUT:0:300}"
fi

# ===================================================================
# Test 5: Graceful exit when project files are missing
# ===================================================================
echo "Test 5: Graceful exit when project files are missing"

TEST_DIR=$(make_test_project)
# Deliberately don't create STATUS.md, BACKLOG.md, DECISIONS.md

export CLAUDE_PROJECT_DIR="$TEST_DIR"
OUTPUT=$(hook_input "test_missing" "startup" | "$HOOK_SCRIPT" 2>/dev/null)
EXIT_CODE=$?

TESTS_RUN=$((TESTS_RUN + 1))
if [[ $EXIT_CODE -eq 0 ]]; then
  pass "Exits 0 when all project files are missing"
else
  fail "Exits 0 when all project files are missing" "exit 0" "exit $EXIT_CODE"
fi

TESTS_RUN=$((TESTS_RUN + 1))
if echo "$OUTPUT" | grep -qi "session context\|${PROJECT_ID}\|WARNING"; then
  pass "Still outputs something useful (header or warning)"
else
  fail "Still outputs something useful" "some output with header or warning" "output: ${OUTPUT:0:200}"
fi

# ===================================================================
# Test 6: Hook completes within 5 seconds
# ===================================================================
echo "Test 6: Hook completes within 5 seconds"
TESTS_RUN=$((TESTS_RUN + 1))

export CLAUDE_PROJECT_DIR="$PROJECT_DIR"
START_TIME=$(python3 -c "import time; print(time.time())")
OUTPUT=$(hook_input "test_perf" "startup" | "$HOOK_SCRIPT" 2>/dev/null)
END_TIME=$(python3 -c "import time; print(time.time())")
ELAPSED=$(python3 -c "print(f'{$END_TIME - $START_TIME:.2f}')")

if python3 -c "exit(0 if $END_TIME - $START_TIME < 5.0 else 1)"; then
  pass "Hook completed in ${ELAPSED}s (limit: 5s)"
else
  fail "Hook completed in time" "<5s" "${ELAPSED}s"
fi

# ===================================================================
# Test 7: SessionStart hook registered in settings.json
# ===================================================================
echo "Test 7: SessionStart hook registered in settings.json"

SETTINGS_FILE="$PROJECT_DIR/.claude/settings.json"

TESTS_RUN=$((TESTS_RUN + 1))
if [[ -f "$SETTINGS_FILE" ]] && grep -q "SessionStart" "$SETTINGS_FILE" 2>/dev/null; then
  pass "SessionStart hook registered in settings.json"
else
  fail "SessionStart hook registered" "SessionStart in settings.json" "not found"
fi

TESTS_RUN=$((TESTS_RUN + 1))
if grep -q "sync-context.sh" "$SETTINGS_FILE" 2>/dev/null; then
  pass "sync-context.sh referenced in settings.json"
else
  fail "sync-context.sh referenced" "sync-context.sh in settings.json" "not found"
fi

# ===================================================================
# Test 8: Outputs agent pipeline status from STATUS.md
# ===================================================================
echo "Test 8: Outputs agent pipeline status from STATUS.md"

TEST_DIR=$(make_test_project)
cat > "$TEST_DIR/STATUS.md" << 'EOF'
# Project Status
**Current Phase:** Testing
**Last Updated:** 2026-02-14

## Agent Pipeline Status

| Agent | Definition | Trigger | Status |
|-------|-----------|---------|--------|
| Scrum Master | .dev-context/agents/scrum_master.md | /sprint | Ready |
| CFO | .dev-context/agents/cfo.md | Hourly | Ready |
EOF

export CLAUDE_PROJECT_DIR="$TEST_DIR"
OUTPUT=$(hook_input "test_agents" "startup" | "$HOOK_SCRIPT" 2>/dev/null)

TESTS_RUN=$((TESTS_RUN + 1))
if echo "$OUTPUT" | grep -q "Agent Pipeline\|Scrum Master"; then
  pass "Output includes agent pipeline status"
else
  fail "Output includes agent pipeline status" "contains agent info" "output: ${OUTPUT:0:300}"
fi

# ===================================================================
# Test 9: Resume/compact sessions include context recovery note
# ===================================================================
echo "Test 9: Resume/compact sessions include context recovery note"

TEST_DIR=$(make_test_project)
cat > "$TEST_DIR/STATUS.md" << 'EOF'
# Status
**Current Phase:** Testing
**Last Updated:** 2026-02-14
EOF

export CLAUDE_PROJECT_DIR="$TEST_DIR"
OUTPUT=$(hook_input "test_compact" "compact" | "$HOOK_SCRIPT" 2>/dev/null)

TESTS_RUN=$((TESTS_RUN + 1))
if echo "$OUTPUT" | grep -qi "context was compacted\|context recovery\|re-read"; then
  pass "Compact session includes context recovery note"
else
  fail "Compact session includes recovery note" "contains recovery instruction" "output: ${OUTPUT:0:200}"
fi

# ===================================================================
# Test 10: Generates web-context.md
# ===================================================================
echo "Test 10: Generates web-context.md"

TEST_DIR=$(make_test_project)
cat > "$TEST_DIR/STATUS.md" << 'EOF'
# Status
**Current Phase:** Testing
**Last Updated:** 2026-02-14

### Next Steps
1. Merge PRs
2. Execute dry run
EOF
cat > "$TEST_DIR/BACKLOG.md" << EOF
# Backlog
## Ready
- [ ] **${PROJECT_ID}-037**: Gateway Sync
  - Priority: P1
- [ ] **${PROJECT_ID}-038**: Snapshots
  - Priority: P2
EOF
cat > "$TEST_DIR/.dev-context/DECISIONS.md" << EOF
# Decisions
## ${PROJECT_ID}-D014: Gateway Sync
**Status**: accepted
**Decision**: Add Gateway Sync agent.
EOF

export CLAUDE_PROJECT_DIR="$TEST_DIR"
hook_input "test_web" "startup" | "$HOOK_SCRIPT" >/dev/null 2>/dev/null

WEB_FILE="$TEST_DIR/.dev-context/web-context.md"
TESTS_RUN=$((TESTS_RUN + 1))
if [[ -f "$WEB_FILE" ]]; then
  pass "web-context.md was generated"
else
  fail "web-context.md was generated" "file exists" "not found"
fi

TESTS_RUN=$((TESTS_RUN + 1))
WEB_CONTENT=$(cat "$WEB_FILE" 2>/dev/null || echo "")
if echo "$WEB_CONTENT" | grep -q "Current Phase" && echo "$WEB_CONTENT" | grep -q "${PROJECT_ID}-037"; then
  pass "web-context.md contains status and top backlog"
else
  fail "web-context.md contains key sections" "status + backlog" "content: ${WEB_CONTENT:0:200}"
fi

TESTS_RUN=$((TESTS_RUN + 1))
if echo "$WEB_CONTENT" | grep -qi "last synced\|generated"; then
  pass "web-context.md has timestamp"
else
  fail "web-context.md has timestamp" "contains timestamp" "content: ${WEB_CONTENT:0:200}"
fi

# ===================================================================
# Test 11: Generates mobile-context.md (ultra-compact)
# ===================================================================
echo "Test 11: Generates mobile-context.md (ultra-compact)"

TEST_DIR=$(make_test_project)
cat > "$TEST_DIR/STATUS.md" << 'EOF'
# Status
**Current Phase:** Testing
**Last Updated:** 2026-02-14

### Next Steps
1. Merge PRs
2. Execute dry run

## Known Issues
- Known issue placeholder
EOF
cat > "$TEST_DIR/BACKLOG.md" << EOF
# Backlog
## Ready
- [ ] **${PROJECT_ID}-037**: Gateway Sync
  - Priority: P1
- [ ] **${PROJECT_ID}-038**: Snapshots
  - Priority: P2
- [ ] **${PROJECT_ID}-039**: PM spec
  - Priority: P1
- [ ] **${PROJECT_ID}-040**: PRD skill
  - Priority: P2
EOF

export CLAUDE_PROJECT_DIR="$TEST_DIR"
hook_input "test_mobile" "startup" | "$HOOK_SCRIPT" >/dev/null 2>/dev/null

MOBILE_FILE="$TEST_DIR/.dev-context/mobile-context.md"
TESTS_RUN=$((TESTS_RUN + 1))
if [[ -f "$MOBILE_FILE" ]]; then
  pass "mobile-context.md was generated"
else
  fail "mobile-context.md was generated" "file exists" "not found"
fi

TESTS_RUN=$((TESTS_RUN + 1))
MOBILE_CONTENT=$(cat "$MOBILE_FILE" 2>/dev/null || echo "")
TICKET_COUNT=$(echo "$MOBILE_CONTENT" | grep -c "${PROJECT_ID}-" || echo "0")
if [[ $TICKET_COUNT -le 4 ]]; then
  pass "mobile-context.md is compact (<=4 ticket references)"
else
  fail "mobile-context.md is compact" "<=4 ticket references" "$TICKET_COUNT references"
fi

TESTS_RUN=$((TESTS_RUN + 1))
if echo "$MOBILE_CONTENT" | grep -qi "approver\|quick decisions\|approval"; then
  pass "mobile-context.md has approval-focused role"
else
  fail "mobile-context.md has approval role" "contains 'approval' focus" "content: ${MOBILE_CONTENT:0:200}"
fi

# ===================================================================
# Test 12: Generates api-context.json (machine-readable)
# ===================================================================
echo "Test 12: Generates api-context.json (machine-readable)"

TEST_DIR=$(make_test_project)
cat > "$TEST_DIR/STATUS.md" << 'EOF'
# Status
**Current Phase:** Testing
**Last Updated:** 2026-02-14
EOF
cat > "$TEST_DIR/BACKLOG.md" << EOF
# Backlog
## Ready
- [ ] **${PROJECT_ID}-037**: Gateway Sync
  - Priority: P1
EOF

export CLAUDE_PROJECT_DIR="$TEST_DIR"
hook_input "test_api" "startup" | "$HOOK_SCRIPT" >/dev/null 2>/dev/null

API_FILE="$TEST_DIR/.dev-context/api-context.json"
TESTS_RUN=$((TESTS_RUN + 1))
if [[ -f "$API_FILE" ]]; then
  pass "api-context.json was generated"
else
  fail "api-context.json was generated" "file exists" "not found"
fi

TESTS_RUN=$((TESTS_RUN + 1))
if python3 -c "import json; json.load(open('$API_FILE'))" 2>/dev/null; then
  pass "api-context.json is valid JSON"
else
  fail "api-context.json is valid JSON" "valid JSON" "invalid"
fi

TESTS_RUN=$((TESTS_RUN + 1))
if python3 -c "
import json
data = json.load(open('$API_FILE'))
assert 'project_id' in data
assert 'last_synced' in data
assert 'current_phase' in data
print('ok')
" 2>/dev/null | grep -q "ok"; then
  pass "api-context.json has required fields"
else
  fail "api-context.json has required fields" "project_id, last_synced, current_phase" "missing fields"
fi

# ===================================================================
# Test 13: Drift detection regenerates stale snapshots
# ===================================================================
echo "Test 13: Drift detection regenerates stale snapshots"

TEST_DIR=$(make_test_project)
cat > "$TEST_DIR/STATUS.md" << 'EOF'
# Status
**Current Phase:** Testing
**Last Updated:** 2026-02-14
EOF

# Create a stale web-context.md (touch with old timestamp)
cat > "$TEST_DIR/.dev-context/web-context.md" << 'EOF'
# Old Context
Last synced: 2026-02-13T06:00:00Z
EOF
# Set modification time to 5 hours ago (macOS syntax)
touch -t "$(date -v-5H +%Y%m%d%H%M.%S 2>/dev/null || date -d '5 hours ago' +%Y%m%d%H%M.%S 2>/dev/null)" "$TEST_DIR/.dev-context/web-context.md" 2>/dev/null || true

export CLAUDE_PROJECT_DIR="$TEST_DIR"
OUTPUT=$(hook_input "test_drift" "startup" | "$HOOK_SCRIPT" 2>/dev/null)

TESTS_RUN=$((TESTS_RUN + 1))
WEB_FILE="$TEST_DIR/.dev-context/web-context.md"
if [[ -f "$WEB_FILE" ]]; then
  WEB_CONTENT=$(cat "$WEB_FILE")
  TODAY=$(date -u +"%Y-%m-%d")
  if echo "$WEB_CONTENT" | grep -q "$TODAY"; then
    pass "Stale web-context.md was regenerated with fresh timestamp"
  else
    fail "Stale snapshot was regenerated" "contains today's date" "content: ${WEB_CONTENT:0:200}"
  fi
else
  fail "web-context.md exists after drift refresh" "file exists" "not found"
fi

# ===================================================================
# Test 14: CLAUDE.md is NOT modified
# ===================================================================
echo "Test 14: CLAUDE.md is not modified by the hook"

TEST_DIR=$(make_test_project)
cat > "$TEST_DIR/STATUS.md" << 'EOF'
# Status
**Current Phase:** Testing
**Last Updated:** 2026-02-14
EOF
cat > "$TEST_DIR/CLAUDE.md" << 'EOF'
# Original CLAUDE.md content — DO NOT MODIFY
This is the human-maintained project instructions file.
EOF

ORIGINAL_HASH=$(md5 -q "$TEST_DIR/CLAUDE.md" 2>/dev/null || md5sum "$TEST_DIR/CLAUDE.md" 2>/dev/null | cut -d' ' -f1)

export CLAUDE_PROJECT_DIR="$TEST_DIR"
hook_input "test_claude_md" "startup" | "$HOOK_SCRIPT" >/dev/null 2>/dev/null

AFTER_HASH=$(md5 -q "$TEST_DIR/CLAUDE.md" 2>/dev/null || md5sum "$TEST_DIR/CLAUDE.md" 2>/dev/null | cut -d' ' -f1)

TESTS_RUN=$((TESTS_RUN + 1))
if [[ "$ORIGINAL_HASH" == "$AFTER_HASH" ]]; then
  pass "CLAUDE.md was not modified"
else
  fail "CLAUDE.md was not modified" "unchanged hash" "hash changed"
fi

# ===================================================================
# Test 15: Full integration — stdout + all 3 snapshot files
# ===================================================================
echo "Test 15: Full integration — stdout + all 3 snapshot files"

TEST_DIR=$(make_test_project)
mkdir -p "$TEST_DIR/.dev-context/inbox/critical"
mkdir -p "$TEST_DIR/.dev-context/inbox/approval"
mkdir -p "$TEST_DIR/.dev-context/inbox/digest"
mkdir -p "$TEST_DIR/.dev-context/inbox/archive"

cat > "$TEST_DIR/.dev-context/project.conf" << EOF
PROJECT_ID=${PROJECT_ID}
PROJECT_NAME=test_project
EOF
cat > "$TEST_DIR/STATUS.md" << 'EOF'
# Project Status
**Current Phase:** Integration Testing
**Last Updated:** 2026-02-14

### Next Steps
1. Run all tests
2. Deploy

## Agent Pipeline Status
| Agent | Status |
|-------|--------|
| Scrum Master | Ready |

## Known Issues
- Test blocker
EOF
cat > "$TEST_DIR/BACKLOG.md" << EOF
# Backlog
## Ready
- [ ] **${PROJECT_ID}-037**: Gateway Sync
  - Priority: P1
- [ ] **${PROJECT_ID}-038**: Snapshots
  - Priority: P2
EOF
cat > "$TEST_DIR/.dev-context/DECISIONS.md" << EOF
# Decisions
## ${PROJECT_ID}-D001: Test Decision
**Status**: accepted
EOF

cat > "$TEST_DIR/.dev-context/inbox/approval/2026-02-14T10-00-pm-test.md" << 'EOF'
# Test PRD
**From**: Product Manager
**Status**: PENDING
EOF

export CLAUDE_PROJECT_DIR="$TEST_DIR"
OUTPUT=$(hook_input "test_full" "startup" | "$HOOK_SCRIPT" 2>/dev/null)
EXIT_CODE=$?

TESTS_RUN=$((TESTS_RUN + 1))
if [[ $EXIT_CODE -eq 0 ]]; then
  pass "Full integration exits 0"
else
  fail "Full integration exits 0" "exit 0" "exit $EXIT_CODE"
fi

TESTS_RUN=$((TESTS_RUN + 1))
if echo "$OUTPUT" | grep -q "Integration Testing"; then
  pass "Stdout contains project phase"
else
  fail "Stdout contains project phase" "contains 'Integration Testing'" "output: ${OUTPUT:0:200}"
fi

for f in web-context.md mobile-context.md api-context.json; do
  TESTS_RUN=$((TESTS_RUN + 1))
  if [[ -f "$TEST_DIR/.dev-context/$f" ]]; then
    pass "$f was generated"
  else
    fail "$f was generated" "file exists" "not found"
  fi
done

# Reset CLAUDE_PROJECT_DIR
unset CLAUDE_PROJECT_DIR

# --- Summary ---
echo ""
echo "============================="
echo "  Tests run:    $TESTS_RUN"
echo "  Passed:       $TESTS_PASSED"
echo "  Failed:       $TESTS_FAILED"
echo "============================="

if [[ $TESTS_FAILED -gt 0 ]]; then
  exit 1
else
  exit 0
fi
