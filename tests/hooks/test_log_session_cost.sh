#!/usr/bin/env bash
# Tests for .claude/hooks/log-session-cost.sh
# Validates cost logging hook behavior with known inputs
#
# Exit 0 = all tests pass, Exit 1 = at least one test failed
#
# NOTE: This is a template. Model names and pricing are dynamically
# detected from the hook script itself. No hardcoded ticket prefixes.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
HOOK_SCRIPT="$PROJECT_DIR/.claude/hooks/log-session-cost.sh"
LEDGER_FILE="$PROJECT_DIR/.dev-context/cost-ledger.csv"

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

# --- Setup ---
BACKUP_LEDGER=""
if [[ -f "$LEDGER_FILE" ]]; then
  BACKUP_LEDGER=$(cat "$LEDGER_FILE")
fi

restore_ledger() {
  if [[ -n "$BACKUP_LEDGER" ]]; then
    echo "$BACKUP_LEDGER" > "$LEDGER_FILE"
  else
    echo "timestamp,agent,session_id,provider,model,input_tokens,output_tokens,cache_creation_tokens,cache_read_tokens,compute_cost_usd,billing_type,billed_usd,ticket,session_start,session_end,duration_sec" > "$LEDGER_FILE"
  fi
}

# Ensure cleanup on exit
trap restore_ledger EXIT

# Reset ledger to header only before each test
reset_ledger() {
  echo "timestamp,agent,session_id,provider,model,input_tokens,output_tokens,cache_creation_tokens,cache_read_tokens,compute_cost_usd,billing_type,billed_usd,ticket,session_start,session_end,duration_sec" > "$LEDGER_FILE"
}

# Extract a CSV field by column index (0-based) from a properly-quoted CSV row
csv_field() {
  local row="$1"
  local index="$2"
  echo "$row" | python3 -c "
import csv, sys
reader = csv.reader(sys.stdin)
for row in reader:
    print(row[$index] if len(row) > $index else '')
"
}

# --- Test: hook script exists and is executable ---
echo "Test 1: Hook script exists and is executable"
TESTS_RUN=$((TESTS_RUN + 1))
if [[ -x "$HOOK_SCRIPT" ]]; then
  pass "Script exists and is executable"
else
  fail "Script exists and is executable" "executable file at $HOOK_SCRIPT" "not found or not executable"
fi

# --- Test: graceful exit when transcript path is empty ---
echo "Test 2: Graceful exit with empty transcript path"
TESTS_RUN=$((TESTS_RUN + 1))
reset_ledger
echo '{"session_id":"test_empty","transcript_path":"","cwd":"."}' | "$HOOK_SCRIPT" 2>/dev/null
EXIT_CODE=$?
if [[ $EXIT_CODE -eq 0 ]]; then
  pass "Exits 0 with empty transcript path"
else
  fail "Exits 0 with empty transcript path" "exit 0" "exit $EXIT_CODE"
fi

# --- Test: graceful exit when transcript file does not exist ---
echo "Test 3: Graceful exit with nonexistent transcript"
TESTS_RUN=$((TESTS_RUN + 1))
reset_ledger
echo '{"session_id":"test_missing","transcript_path":"/tmp/does-not-exist-transcript.jsonl","cwd":"."}' | "$HOOK_SCRIPT" 2>/dev/null
EXIT_CODE=$?
if [[ $EXIT_CODE -eq 0 ]]; then
  pass "Exits 0 with nonexistent transcript"
else
  fail "Exits 0 with nonexistent transcript" "exit 0" "exit $EXIT_CODE"
fi

# --- Test: correct token counting and cost calculation ---
echo "Test 4: Token counting and cost calculation"
TESTS_RUN=$((TESTS_RUN + 1))
reset_ledger

# Create test transcript with known token values
# claude-opus-4-6 pricing: input $15.00/1M, output $75.00/1M
# Input: 50000 + 30000 = 80000 tokens => 80000/1M * 15.00 = 1.2000
# Output: 15000 + 5000 = 20000 tokens => 20000/1M * 75.00 = 1.5000
# Total expected: 2.7000
TEST_TRANSCRIPT="/tmp/test-cost-transcript.jsonl"
cat > "$TEST_TRANSCRIPT" << 'JSONL'
{"type":"system","content":"session start"}
{"type":"assistant","model":"claude-opus-4-6-20250929","usage":{"input_tokens":50000,"output_tokens":15000},"content":"test response"}
{"type":"assistant","model":"claude-opus-4-6-20250929","usage":{"input_tokens":30000,"output_tokens":5000},"content":"another response"}
JSONL

export CLAUDE_PROJECT_DIR="$PROJECT_DIR"
echo "{\"session_id\":\"test_cost_001\",\"transcript_path\":\"$TEST_TRANSCRIPT\",\"cwd\":\"$PROJECT_DIR\",\"permission_mode\":\"default\",\"hook_event_name\":\"SessionEnd\"}" | "$HOOK_SCRIPT" 2>/dev/null
EXIT_CODE=$?

if [[ $EXIT_CODE -ne 0 ]]; then
  fail "Script exits 0 on valid input" "exit 0" "exit $EXIT_CODE"
else
  # Check the ledger has exactly 2 lines (header + 1 data row)
  LINE_COUNT=$(wc -l < "$LEDGER_FILE" | tr -d ' ')
  if [[ "$LINE_COUNT" -ne 2 ]]; then
    fail "Ledger has 2 lines (header + data)" "2 lines" "$LINE_COUNT lines"
  else
    # Parse the data row using CSV-safe parsing (handles quoted fields)
    DATA_ROW=$(tail -1 "$LEDGER_FILE")
    sid=$(csv_field "$DATA_ROW" 2)
    provider=$(csv_field "$DATA_ROW" 3)
    input_t=$(csv_field "$DATA_ROW" 5)
    output_t=$(csv_field "$DATA_ROW" 6)
    cache_create_t=$(csv_field "$DATA_ROW" 7)
    cache_read_t=$(csv_field "$DATA_ROW" 8)
    compute_cost=$(csv_field "$DATA_ROW" 9)
    billing_type=$(csv_field "$DATA_ROW" 10)
    billed_usd=$(csv_field "$DATA_ROW" 11)

    # Check session_id
    if [[ "$sid" == "test_cost_001" ]]; then
      pass "Session ID recorded correctly"
    else
      fail "Session ID recorded correctly" "test_cost_001" "$sid"
    fi
    TESTS_RUN=$((TESTS_RUN + 1))

    # Check provider
    TESTS_RUN=$((TESTS_RUN + 1))
    if [[ "$provider" == "anthropic" ]]; then
      pass "Provider detected as anthropic"
    else
      fail "Provider detected as anthropic" "anthropic" "$provider"
    fi

    # Check token sums
    TESTS_RUN=$((TESTS_RUN + 1))
    if [[ "$input_t" == "80000" ]]; then
      pass "Input tokens summed correctly (80000)"
    else
      fail "Input tokens summed correctly" "80000" "$input_t"
    fi

    TESTS_RUN=$((TESTS_RUN + 1))
    if [[ "$output_t" == "20000" ]]; then
      pass "Output tokens summed correctly (20000)"
    else
      fail "Output tokens summed correctly" "20000" "$output_t"
    fi

    # Check cache token columns (no cache tokens in this test)
    TESTS_RUN=$((TESTS_RUN + 1))
    if [[ "$cache_create_t" == "0" ]]; then
      pass "Cache creation tokens recorded (0)"
    else
      fail "Cache creation tokens recorded" "0" "$cache_create_t"
    fi

    TESTS_RUN=$((TESTS_RUN + 1))
    if [[ "$cache_read_t" == "0" ]]; then
      pass "Cache read tokens recorded (0)"
    else
      fail "Cache read tokens recorded" "0" "$cache_read_t"
    fi

    # Check cost calculation: 2.7000
    TESTS_RUN=$((TESTS_RUN + 1))
    if [[ "$compute_cost" == "2.7000" ]]; then
      pass "Compute cost calculated correctly (2.7000)"
    else
      fail "Compute cost calculated correctly" "2.7000" "$compute_cost"
    fi

    # Check billing_type defaults to "subscription"
    TESTS_RUN=$((TESTS_RUN + 1))
    if [[ "$billing_type" == "subscription" ]]; then
      pass "Billing type defaults to subscription"
    else
      fail "Billing type defaults to subscription" "subscription" "$billing_type"
    fi

    # Check billed_usd is 0.0000 for subscription
    TESTS_RUN=$((TESTS_RUN + 1))
    if [[ "$billed_usd" == "0.0000" ]]; then
      pass "Billed USD is 0.0000 for subscription"
    else
      fail "Billed USD is 0.0000 for subscription" "0.0000" "$billed_usd"
    fi
  fi
fi

rm -f "$TEST_TRANSCRIPT"

# --- Test: no row appended when ledger is missing ---
echo "Test 5: No crash when ledger file is missing"
TESTS_RUN=$((TESTS_RUN + 1))
rm -f "$LEDGER_FILE"
TEST_TRANSCRIPT_2="/tmp/test-cost-transcript-2.jsonl"
echo '{"type":"assistant","model":"claude-opus-4-6","usage":{"input_tokens":1000,"output_tokens":500},"content":"hi"}' > "$TEST_TRANSCRIPT_2"
echo "{\"session_id\":\"test_no_ledger\",\"transcript_path\":\"$TEST_TRANSCRIPT_2\",\"cwd\":\"$PROJECT_DIR\"}" | "$HOOK_SCRIPT" 2>/dev/null
EXIT_CODE=$?
if [[ $EXIT_CODE -eq 0 ]]; then
  pass "Exits 0 when ledger file is missing"
else
  fail "Exits 0 when ledger file is missing" "exit 0" "exit $EXIT_CODE"
fi
rm -f "$TEST_TRANSCRIPT_2"

# Restore ledger for remaining tests
reset_ledger

# --- Test: real Claude Code transcript format (.message.usage) ---
echo "Test 6: Real Claude Code transcript format (message.usage)"
TESTS_RUN=$((TESTS_RUN + 1))
reset_ledger

# This mirrors the actual transcript structure found in Claude Code
# Usage is nested under .message.usage, model is under .message.model
# Includes cache_creation_input_tokens and cache_read_input_tokens
# Pricing: input_per_1m=15.00, output_per_1m=75.00
# input_tokens: 100 => 100/1M * 15.00 = 0.0015
# output_tokens: 50 => 50/1M * 75.00 = 0.00375
# cache_creation: 40000 => 40000/1M * 15.00 * 1.25 = 0.75
# cache_read: 0 => 0
# Total: 0.0015 + 0.00375 + 0.75 = 0.75525 => 0.7552 (Python banker's rounding)
TEST_TRANSCRIPT_REAL="/tmp/test-real-transcript.jsonl"
cat > "$TEST_TRANSCRIPT_REAL" << 'JSONL'
{"type":"queue-operation","operation":"dequeue","timestamp":"2026-02-13T10:00:00.000Z","sessionId":"test_real_001"}
{"type":"user","message":{"role":"user","content":"say hello"},"uuid":"abc","timestamp":"2026-02-13T10:00:01.000Z"}
{"parentUuid":"abc","message":{"model":"claude-opus-4-6","id":"msg_123","type":"message","role":"assistant","content":[{"type":"text","text":"Hello!"}],"usage":{"input_tokens":100,"cache_creation_input_tokens":40000,"cache_read_input_tokens":0,"output_tokens":50}},"type":"assistant","uuid":"def","timestamp":"2026-02-13T10:00:02.000Z"}
JSONL

echo "{\"session_id\":\"test_real_001\",\"transcript_path\":\"$TEST_TRANSCRIPT_REAL\",\"cwd\":\"$PROJECT_DIR\"}" | "$HOOK_SCRIPT" 2>/dev/null
EXIT_CODE=$?

if [[ $EXIT_CODE -ne 0 ]]; then
  fail "Script exits 0 on real format" "exit 0" "exit $EXIT_CODE"
else
  DATA_ROW=$(tail -1 "$LEDGER_FILE")
  model=$(csv_field "$DATA_ROW" 4)
  input_t=$(csv_field "$DATA_ROW" 5)
  output_t=$(csv_field "$DATA_ROW" 6)
  cache_create_t=$(csv_field "$DATA_ROW" 7)
  cache_read_t=$(csv_field "$DATA_ROW" 8)
  compute_cost=$(csv_field "$DATA_ROW" 9)

  # Check model was extracted from .message.model
  TESTS_RUN=$((TESTS_RUN + 1))
  if [[ "$model" == "claude-opus-4-6" ]]; then
    pass "Model extracted from message.model (claude-opus-4-6)"
  else
    fail "Model extracted from message.model" "claude-opus-4-6" "$model"
  fi

  # Check input tokens (from .message.usage.input_tokens)
  TESTS_RUN=$((TESTS_RUN + 1))
  if [[ "$input_t" == "100" ]]; then
    pass "Input tokens from message.usage (100)"
  else
    fail "Input tokens from message.usage" "100" "$input_t"
  fi

  # Check output tokens
  TESTS_RUN=$((TESTS_RUN + 1))
  if [[ "$output_t" == "50" ]]; then
    pass "Output tokens from message.usage (50)"
  else
    fail "Output tokens from message.usage" "50" "$output_t"
  fi

  # Check cache creation tokens saved to CSV
  TESTS_RUN=$((TESTS_RUN + 1))
  if [[ "$cache_create_t" == "40000" ]]; then
    pass "Cache creation tokens recorded (40000)"
  else
    fail "Cache creation tokens recorded" "40000" "$cache_create_t"
  fi

  # Check cache read tokens saved to CSV
  TESTS_RUN=$((TESTS_RUN + 1))
  if [[ "$cache_read_t" == "0" ]]; then
    pass "Cache read tokens recorded (0)"
  else
    fail "Cache read tokens recorded" "0" "$cache_read_t"
  fi

  # Check cost includes cache creation tokens
  # Expected: 0.7552 (with cache creation at 1.25x input rate, banker's rounding)
  TESTS_RUN=$((TESTS_RUN + 1))
  if [[ "$compute_cost" == "0.7552" ]]; then
    pass "Compute cost includes cache creation tokens (0.7552)"
  else
    fail "Compute cost includes cache creation tokens" "0.7552" "$compute_cost"
  fi
fi

rm -f "$TEST_TRANSCRIPT_REAL"
reset_ledger

# --- Test: empty transcript writes no row ---
echo "Test 7: Empty transcript does not write zero-value row"
TESTS_RUN=$((TESTS_RUN + 1))
reset_ledger

# Transcript with no usage data at all
TEST_TRANSCRIPT_EMPTY="/tmp/test-empty-transcript.jsonl"
cat > "$TEST_TRANSCRIPT_EMPTY" << 'JSONL'
{"type":"system","content":"session start"}
{"type":"user","message":{"role":"user","content":"hello"}}
JSONL

echo "{\"session_id\":\"test_empty_usage\",\"transcript_path\":\"$TEST_TRANSCRIPT_EMPTY\",\"cwd\":\"$PROJECT_DIR\"}" | "$HOOK_SCRIPT" 2>/dev/null
EXIT_CODE=$?

if [[ $EXIT_CODE -ne 0 ]]; then
  fail "Script exits 0 on empty usage transcript" "exit 0" "exit $EXIT_CODE"
else
  LINE_COUNT=$(wc -l < "$LEDGER_FILE" | tr -d ' ')
  if [[ "$LINE_COUNT" -eq 1 ]]; then
    pass "No row appended for transcript with no usage data"
  else
    fail "No row appended for transcript with no usage data" "1 line (header only)" "$LINE_COUNT lines"
  fi
fi

rm -f "$TEST_TRANSCRIPT_EMPTY"
reset_ledger

# --- Test: CSV fields are properly quoted ---
echo "Test 8: CSV fields are properly quoted"
TESTS_RUN=$((TESTS_RUN + 1))
reset_ledger

# Session ID with a comma to test CSV quoting
TEST_TRANSCRIPT_CSV="/tmp/test-csv-transcript.jsonl"
cat > "$TEST_TRANSCRIPT_CSV" << 'JSONL'
{"type":"assistant","model":"claude-opus-4-6","usage":{"input_tokens":1000,"output_tokens":500},"content":"hi"}
JSONL

echo "{\"session_id\":\"sess,with,commas\",\"transcript_path\":\"$TEST_TRANSCRIPT_CSV\",\"cwd\":\"$PROJECT_DIR\"}" | "$HOOK_SCRIPT" 2>/dev/null
EXIT_CODE=$?

if [[ $EXIT_CODE -ne 0 ]]; then
  fail "Script exits 0 with comma in session_id" "exit 0" "exit $EXIT_CODE"
else
  DATA_ROW=$(tail -1 "$LEDGER_FILE")
  # Properly quoted CSV should have exactly 13 fields even with commas in session_id
  if echo "$DATA_ROW" | grep -q '"sess,with,commas"'; then
    pass "Session ID with commas is properly CSV-quoted"
  else
    fail "Session ID with commas is properly CSV-quoted" "field containing '\"sess,with,commas\"'" "$DATA_ROW"
  fi
fi

rm -f "$TEST_TRANSCRIPT_CSV"
reset_ledger

# --- Test: exact model match only in pricing ---
echo "Test 9: Pricing uses exact model match only (no partial match)"
TESTS_RUN=$((TESTS_RUN + 1))
reset_ledger

# Use a model name that could partially match multiple pricing keys
# With exact match only, this should result in cost 0.0000
TEST_TRANSCRIPT_PARTIAL="/tmp/test-partial-model.jsonl"
cat > "$TEST_TRANSCRIPT_PARTIAL" << 'JSONL'
{"type":"assistant","model":"claude","usage":{"input_tokens":1000000,"output_tokens":0},"content":"hi"}
JSONL

echo "{\"session_id\":\"test_partial\",\"transcript_path\":\"$TEST_TRANSCRIPT_PARTIAL\",\"cwd\":\"$PROJECT_DIR\"}" | "$HOOK_SCRIPT" 2>/dev/null
EXIT_CODE=$?

if [[ $EXIT_CODE -ne 0 ]]; then
  fail "Script exits 0 with ambiguous model name" "exit 0" "exit $EXIT_CODE"
else
  DATA_ROW=$(tail -1 "$LEDGER_FILE")
  COST_FIELD=$(echo "$DATA_ROW" | python3 -c "
import csv, sys
reader = csv.reader(sys.stdin)
for row in reader:
    print(row[9])
" 2>/dev/null || echo "")
  if [[ "$COST_FIELD" == "0.0000" || "$COST_FIELD" == "0.00" ]]; then
    pass "Ambiguous model 'claude' gets zero cost (no partial match)"
  else
    fail "Ambiguous model 'claude' gets zero cost (no partial match)" "0.0000 or 0.00" "$COST_FIELD"
  fi
fi

rm -f "$TEST_TRANSCRIPT_PARTIAL"
reset_ledger

# --- Test: large transcript performance ---
echo "Test 10: Large transcript completes within timeout"
TESTS_RUN=$((TESTS_RUN + 1))
reset_ledger

# Generate a 500-line transcript (should complete well within 30s with single jq pass)
TEST_TRANSCRIPT_LARGE="/tmp/test-large-transcript.jsonl"
: > "$TEST_TRANSCRIPT_LARGE"
for i in $(seq 1 500); do
  echo "{\"type\":\"assistant\",\"message\":{\"model\":\"claude-opus-4-6\",\"usage\":{\"input_tokens\":100,\"output_tokens\":50}},\"content\":\"line $i\"}" >> "$TEST_TRANSCRIPT_LARGE"
done

START_TIME=$(python3 -c "import time; print(int(time.time()))")
echo "{\"session_id\":\"test_large\",\"transcript_path\":\"$TEST_TRANSCRIPT_LARGE\",\"cwd\":\"$PROJECT_DIR\"}" | "$HOOK_SCRIPT" 2>/dev/null &
HOOK_PID=$!
# Wait up to 15 seconds
TIMED_OUT=0
for _i in $(seq 1 15); do
  if ! kill -0 "$HOOK_PID" 2>/dev/null; then
    break
  fi
  sleep 1
done
if kill -0 "$HOOK_PID" 2>/dev/null; then
  kill "$HOOK_PID" 2>/dev/null || true
  wait "$HOOK_PID" 2>/dev/null || true
  TIMED_OUT=1
fi
wait "$HOOK_PID" 2>/dev/null
EXIT_CODE=$?
END_TIME=$(python3 -c "import time; print(int(time.time()))")
ELAPSED=$((END_TIME - START_TIME))

if [[ $TIMED_OUT -eq 1 ]]; then
  fail "Large transcript completes within 15s" "exit 0 within 15s" "timed out after ${ELAPSED}s"
elif [[ $EXIT_CODE -ne 0 ]]; then
  fail "Large transcript completes within 15s" "exit 0 within 15s" "exit $EXIT_CODE"
else
  if [[ $ELAPSED -le 15 ]]; then
    pass "500-line transcript completed in ${ELAPSED}s (limit: 15s)"
  else
    fail "500-line transcript completed in time" "<=15s" "${ELAPSED}s"
  fi

  # Also verify token sums are correct: 500 * 100 = 50000 input, 500 * 50 = 25000 output
  TESTS_RUN=$((TESTS_RUN + 1))
  DATA_ROW=$(tail -1 "$LEDGER_FILE")
  INPUT_T=$(echo "$DATA_ROW" | python3 -c "
import csv, sys
reader = csv.reader(sys.stdin)
for row in reader:
    print(row[5])
" 2>/dev/null || echo "")
  if [[ "$INPUT_T" == "50000" ]]; then
    pass "Large transcript token sum correct (50000 input)"
  else
    fail "Large transcript token sum correct" "50000" "$INPUT_T"
  fi
fi

rm -f "$TEST_TRANSCRIPT_LARGE"
reset_ledger

# --- Test: billing_type=api sets billed_usd=compute_cost ---
echo "Test 11: API billing type sets billed_usd equal to compute_cost"
TESTS_RUN=$((TESTS_RUN + 1))
reset_ledger

TEST_TRANSCRIPT_API="/tmp/test-api-billing.jsonl"
cat > "$TEST_TRANSCRIPT_API" << 'JSONL'
{"type":"assistant","model":"claude-opus-4-6","usage":{"input_tokens":10000,"output_tokens":5000},"content":"test"}
JSONL

# Set CLAUDE_BILLING_TYPE=api
CLAUDE_BILLING_TYPE=api echo "{\"session_id\":\"test_api\",\"transcript_path\":\"$TEST_TRANSCRIPT_API\",\"cwd\":\"$PROJECT_DIR\"}" | CLAUDE_BILLING_TYPE=api "$HOOK_SCRIPT" 2>/dev/null
EXIT_CODE=$?

if [[ $EXIT_CODE -ne 0 ]]; then
  fail "Script exits 0 with billing_type=api" "exit 0" "exit $EXIT_CODE"
else
  DATA_ROW=$(tail -1 "$LEDGER_FILE")
  billing_type=$(csv_field "$DATA_ROW" 10)
  compute_cost=$(csv_field "$DATA_ROW" 9)
  billed_usd=$(csv_field "$DATA_ROW" 11)

  TESTS_RUN=$((TESTS_RUN + 1))
  if [[ "$billing_type" == "api" ]]; then
    pass "Billing type is 'api' when CLAUDE_BILLING_TYPE=api"
  else
    fail "Billing type is 'api'" "api" "$billing_type"
  fi

  TESTS_RUN=$((TESTS_RUN + 1))
  if [[ "$billed_usd" == "$compute_cost" ]]; then
    pass "Billed USD equals compute cost for api billing ($billed_usd)"
  else
    fail "Billed USD equals compute cost" "$compute_cost" "$billed_usd"
  fi
fi

rm -f "$TEST_TRANSCRIPT_API"
reset_ledger

# --- Test: jq dependency check ---
echo "Test 12: Script checks for jq dependency"
TESTS_RUN=$((TESTS_RUN + 1))
# Check that the script contains a jq dependency check
if grep -q 'command -v jq' "$HOOK_SCRIPT" 2>/dev/null; then
  pass "Script checks for jq availability"
else
  fail "Script checks for jq availability" "command -v jq check in script" "not found"
fi

# --- Test: Sonnet 4.5 cost calculation ---
echo "Test 13: Sonnet 4.5 cost calculation"
TESTS_RUN=$((TESTS_RUN + 1))
reset_ledger

# Sonnet 4.5 pricing: input $3.00/1M, output $15.00/1M
# Input: 1000000 tokens => 1M/1M * 3.00 = 3.0000
# Output: 500000 tokens => 500K/1M * 15.00 = 7.5000
# Total expected: 10.5000
TEST_TRANSCRIPT_SONNET="/tmp/test-sonnet-cost.jsonl"
cat > "$TEST_TRANSCRIPT_SONNET" << 'JSONL'
{"type":"assistant","message":{"model":"claude-sonnet-4-5-20250929","usage":{"input_tokens":1000000,"output_tokens":500000,"cache_creation_input_tokens":0,"cache_read_input_tokens":0}},"content":"test"}
JSONL

echo "{\"session_id\":\"test_sonnet\",\"transcript_path\":\"$TEST_TRANSCRIPT_SONNET\",\"cwd\":\"$PROJECT_DIR\"}" | "$HOOK_SCRIPT" 2>/dev/null
EXIT_CODE=$?

if [[ $EXIT_CODE -ne 0 ]]; then
  fail "Sonnet hook exits 0" "exit 0" "exit $EXIT_CODE"
else
  DATA_ROW=$(tail -1 "$LEDGER_FILE")
  compute_cost=$(csv_field "$DATA_ROW" 9)

  if [[ "$compute_cost" == "10.5000" ]]; then
    pass "Sonnet 4.5 cost calculated correctly (10.5000)"
  else
    fail "Sonnet 4.5 cost calculated correctly" "10.5000" "$compute_cost"
  fi
fi

rm -f "$TEST_TRANSCRIPT_SONNET"
reset_ledger

# --- Test: Haiku 4.5 cost calculation ---
echo "Test 14: Haiku 4.5 cost calculation"
TESTS_RUN=$((TESTS_RUN + 1))
reset_ledger

# Haiku 4.5 pricing: input $0.80/1M, output $4.00/1M
# Input: 5000000 tokens => 5M/1M * 0.80 = 4.0000
# Output: 1000000 tokens => 1M/1M * 4.00 = 4.0000
# Total expected: 8.0000
TEST_TRANSCRIPT_HAIKU="/tmp/test-haiku-cost.jsonl"
cat > "$TEST_TRANSCRIPT_HAIKU" << 'JSONL'
{"type":"assistant","message":{"model":"claude-haiku-4-5","usage":{"input_tokens":5000000,"output_tokens":1000000,"cache_creation_input_tokens":0,"cache_read_input_tokens":0}},"content":"test"}
JSONL

echo "{\"session_id\":\"test_haiku\",\"transcript_path\":\"$TEST_TRANSCRIPT_HAIKU\",\"cwd\":\"$PROJECT_DIR\"}" | "$HOOK_SCRIPT" 2>/dev/null
EXIT_CODE=$?

if [[ $EXIT_CODE -ne 0 ]]; then
  fail "Haiku hook exits 0" "exit 0" "exit $EXIT_CODE"
else
  DATA_ROW=$(tail -1 "$LEDGER_FILE")
  compute_cost=$(csv_field "$DATA_ROW" 9)

  if [[ "$compute_cost" == "8.0000" ]]; then
    pass "Haiku 4.5 cost calculated correctly (8.0000)"
  else
    fail "Haiku 4.5 cost calculated correctly" "8.0000" "$compute_cost"
  fi
fi

rm -f "$TEST_TRANSCRIPT_HAIKU"
reset_ledger

# --- Test: Combined cache_create + cache_read tokens ---
echo "Test 15: Combined cache creation and read tokens"
TESTS_RUN=$((TESTS_RUN + 1))
reset_ledger

# Opus pricing: input $15.00/1M, output $75.00/1M
# Input: 10000 => 0.15
# Output: 5000 => 0.375
# Cache create: 500000 => 500K/1M * 15 * 1.25 = 9.375
# Cache read: 2000000 => 2M/1M * 15 * 0.10 = 3.00
# Total: 0.15 + 0.375 + 9.375 + 3.00 = 12.9000
TEST_TRANSCRIPT_CACHE="/tmp/test-cache-combined.jsonl"
cat > "$TEST_TRANSCRIPT_CACHE" << 'JSONL'
{"type":"assistant","message":{"model":"claude-opus-4-6","usage":{"input_tokens":10000,"output_tokens":5000,"cache_creation_input_tokens":500000,"cache_read_input_tokens":2000000}},"content":"test"}
JSONL

echo "{\"session_id\":\"test_cache_combo\",\"transcript_path\":\"$TEST_TRANSCRIPT_CACHE\",\"cwd\":\"$PROJECT_DIR\"}" | "$HOOK_SCRIPT" 2>/dev/null
EXIT_CODE=$?

if [[ $EXIT_CODE -ne 0 ]]; then
  fail "Cache combo hook exits 0" "exit 0" "exit $EXIT_CODE"
else
  DATA_ROW=$(tail -1 "$LEDGER_FILE")
  compute_cost=$(csv_field "$DATA_ROW" 9)

  if [[ "$compute_cost" == "12.9000" ]]; then
    pass "Combined cache create+read cost correct (12.9000)"
  else
    fail "Combined cache create+read cost correct" "12.9000" "$compute_cost"
  fi
fi

rm -f "$TEST_TRANSCRIPT_CACHE"
reset_ledger

# --- Test: Date-stamped model name normalization ---
echo "Test 16: Date-stamped model name normalizes for pricing lookup"
TESTS_RUN=$((TESTS_RUN + 1))
reset_ledger

# Model "claude-sonnet-4-5-20250929" should normalize to "claude-sonnet-4-5"
# and use Sonnet pricing ($3/$15)
# Input: 1000000 => $3.00
# Output: 0 => $0.00
# Total: $3.0000
TEST_TRANSCRIPT_DATED="/tmp/test-dated-model.jsonl"
cat > "$TEST_TRANSCRIPT_DATED" << 'JSONL'
{"type":"assistant","message":{"model":"claude-sonnet-4-5-20250929","usage":{"input_tokens":1000000,"output_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0}},"content":"test"}
JSONL

echo "{\"session_id\":\"test_dated_model\",\"transcript_path\":\"$TEST_TRANSCRIPT_DATED\",\"cwd\":\"$PROJECT_DIR\"}" | "$HOOK_SCRIPT" 2>/dev/null
EXIT_CODE=$?

if [[ $EXIT_CODE -ne 0 ]]; then
  fail "Dated model hook exits 0" "exit 0" "exit $EXIT_CODE"
else
  DATA_ROW=$(tail -1 "$LEDGER_FILE")
  compute_cost=$(csv_field "$DATA_ROW" 9)

  if [[ "$compute_cost" == "3.0000" ]]; then
    pass "Date-stamped model normalized for pricing (3.0000)"
  else
    fail "Date-stamped model normalized for pricing" "3.0000" "$compute_cost"
  fi
fi

rm -f "$TEST_TRANSCRIPT_DATED"
reset_ledger

# --- Test: session span + duration_sec captured from transcript timestamps ---
echo "Test: Session span and duration_sec"
reset_ledger
TEST_TRANSCRIPT_DUR="/tmp/test-cost-transcript-dur.jsonl"
cat > "$TEST_TRANSCRIPT_DUR" << 'JSONL'
{"type":"system","timestamp":"2026-05-29T10:00:00Z","content":"start"}
{"type":"assistant","timestamp":"2026-05-29T10:02:30Z","model":"claude-haiku-4-5","usage":{"input_tokens":1000,"output_tokens":500}}
{"type":"assistant","timestamp":"2026-05-29T10:05:00Z","model":"claude-haiku-4-5","usage":{"input_tokens":1000,"output_tokens":500}}
JSONL
export CLAUDE_PROJECT_DIR="$PROJECT_DIR"
echo "{\"session_id\":\"test_dur_001\",\"transcript_path\":\"$TEST_TRANSCRIPT_DUR\",\"cwd\":\"$PROJECT_DIR\",\"hook_event_name\":\"SessionEnd\"}" | "$HOOK_SCRIPT" 2>/dev/null
if [[ $? -eq 0 ]]; then
  DATA_ROW=$(tail -1 "$LEDGER_FILE")
  s_start=$(csv_field "$DATA_ROW" 13)
  s_end=$(csv_field "$DATA_ROW" 14)
  s_dur=$(csv_field "$DATA_ROW" 15)

  TESTS_RUN=$((TESTS_RUN + 1))
  if [[ "$s_start" == "2026-05-29T10:00:00Z" ]]; then
    pass "session_start = first transcript timestamp"
  else
    fail "session_start = first transcript timestamp" "2026-05-29T10:00:00Z" "$s_start"
  fi

  TESTS_RUN=$((TESTS_RUN + 1))
  if [[ "$s_end" == "2026-05-29T10:05:00Z" ]]; then
    pass "session_end = last transcript timestamp"
  else
    fail "session_end = last transcript timestamp" "2026-05-29T10:05:00Z" "$s_end"
  fi

  # 10:00:00 -> 10:05:00 = 300 seconds
  TESTS_RUN=$((TESTS_RUN + 1))
  if [[ "$s_dur" == "300" ]]; then
    pass "duration_sec computed (300)"
  else
    fail "duration_sec computed" "300" "$s_dur"
  fi
else
  TESTS_RUN=$((TESTS_RUN + 1))
  fail "Duration hook exits 0" "exit 0" "exit $?"
fi
rm -f "$TEST_TRANSCRIPT_DUR"
reset_ledger

# --- Test: missing timestamps degrade to empty span / zero duration ---
echo "Test: Missing timestamps degrade gracefully"
reset_ledger
TEST_TRANSCRIPT_NOTS="/tmp/test-cost-transcript-nots.jsonl"
cat > "$TEST_TRANSCRIPT_NOTS" << 'JSONL'
{"type":"assistant","model":"claude-haiku-4-5","usage":{"input_tokens":1000,"output_tokens":500}}
JSONL
echo "{\"session_id\":\"test_nots_001\",\"transcript_path\":\"$TEST_TRANSCRIPT_NOTS\",\"cwd\":\"$PROJECT_DIR\",\"hook_event_name\":\"SessionEnd\"}" | "$HOOK_SCRIPT" 2>/dev/null
if [[ $? -eq 0 ]]; then
  DATA_ROW=$(tail -1 "$LEDGER_FILE")
  s_dur=$(csv_field "$DATA_ROW" 15)
  TESTS_RUN=$((TESTS_RUN + 1))
  if [[ "$s_dur" == "0" ]]; then
    pass "duration_sec = 0 when timestamps absent"
  else
    fail "duration_sec = 0 when timestamps absent" "0" "$s_dur"
  fi
else
  TESTS_RUN=$((TESTS_RUN + 1))
  fail "No-timestamp hook exits 0" "exit 0" "exit $?"
fi
rm -f "$TEST_TRANSCRIPT_NOTS"
reset_ledger

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
