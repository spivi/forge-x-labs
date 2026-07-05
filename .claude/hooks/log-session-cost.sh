#!/usr/bin/env bash
# .claude/hooks/log-session-cost.sh
# Claude Code SessionEnd hook: logs session cost to cost-ledger.csv
#
# Input: JSON on stdin with session_id, transcript_path, cwd
# Output: Appends row to .dev-context/cost-ledger.csv
#
# Required tools: jq, python3

set -euo pipefail

# --- Dependency check ---
command -v jq >/dev/null 2>&1 || { echo "ERROR: jq required for cost logging" >&2; exit 0; }

# --- Configuration ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
LEDGER_FILE="$PROJECT_DIR/.dev-context/cost-ledger.csv"
BUDGETS_FILE="$PROJECT_DIR/.dev-context/budgets.yml"

# --- Read hook input from stdin ---
INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // "unknown"')
TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path // ""')
CWD=$(echo "$INPUT" | jq -r '.cwd // "."')

# --- Guard: skip if no transcript ---
if [[ -z "$TRANSCRIPT_PATH" || ! -f "$TRANSCRIPT_PATH" ]]; then
  exit 0
fi

# --- Guard: skip if ledger doesn't exist (header only) ---
if [[ ! -f "$LEDGER_FILE" ]]; then
  exit 0
fi

# --- Parse transcript for token usage (single jq pass) ---
# Claude Code transcripts are JSONL files. Each line is a JSON object.
# Real format: .message.usage and .message.model (discovered via Task 1.5)
# Legacy/test format: .usage and .model at top level
# Single jq invocation processes entire file at once (O(1) subprocess vs O(N))
read -r TOTAL_INPUT_TOKENS TOTAL_OUTPUT_TOKENS TOTAL_CACHE_CREATION_TOKENS TOTAL_CACHE_READ_TOKENS MODEL < <(
  jq -rs '
    [.[] | select(.message.usage // .usage)]
    | {
        input: [.[].message.usage.input_tokens // .[].usage.input_tokens // 0] | add,
        output: [.[].message.usage.output_tokens // .[].usage.output_tokens // 0] | add,
        cache_create: [.[].message.usage.cache_creation_input_tokens // .[].usage.cache_creation_input_tokens // 0] | add,
        cache_read: [.[].message.usage.cache_read_input_tokens // .[].usage.cache_read_input_tokens // 0] | add,
        model: ([.[].message.model // .[].model // empty] | last // "unknown")
      }
    | "\(.input) \(.output) \(.cache_create) \(.cache_read) \(.model)"
  ' "$TRANSCRIPT_PATH" 2>/dev/null || echo "0 0 0 0 unknown"
)

# --- Extract session span (first/last transcript timestamps) ---
# Every transcript line carries a top-level ISO-8601 .timestamp. The active
# session span (first -> last) is the wall-clock "actual" that /debrief
# calibrates estimate_minutes against. Separate jq pass over ALL lines so
# usage-less lines still contribute to the span. Fail-soft to empty.
read -r SESSION_START SESSION_END < <(
  jq -rs '
    [.[] | .timestamp // empty | select(. != "")] as $ts
    | "\($ts | first // "") \($ts | last // "")"
  ' "$TRANSCRIPT_PATH" 2>/dev/null || echo " "
)
SESSION_START="${SESSION_START:-}"
SESSION_END="${SESSION_END:-}"

# --- Compute duration in seconds (portable ISO-8601 diff via python3) ---
DURATION_SEC="0"
if [[ -n "$SESSION_START" && -n "$SESSION_END" ]]; then
  DURATION_SEC=$(
    CFO_START="$SESSION_START" CFO_END="$SESSION_END" python3 -c '
import os, sys
from datetime import datetime
def parse(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))
try:
    d = (parse(os.environ["CFO_END"]) - parse(os.environ["CFO_START"])).total_seconds()
    print(int(d) if d >= 0 else 0)
except Exception:
    print(0)
' 2>/dev/null || echo "0"
  )
fi
DURATION_SEC=${DURATION_SEC//[!0-9]/}
DURATION_SEC=${DURATION_SEC:-0}

# --- Validate numeric values (default to 0 if non-numeric) ---
TOTAL_INPUT_TOKENS=${TOTAL_INPUT_TOKENS//[!0-9]/}
TOTAL_INPUT_TOKENS=${TOTAL_INPUT_TOKENS:-0}
TOTAL_OUTPUT_TOKENS=${TOTAL_OUTPUT_TOKENS//[!0-9]/}
TOTAL_OUTPUT_TOKENS=${TOTAL_OUTPUT_TOKENS:-0}
TOTAL_CACHE_CREATION_TOKENS=${TOTAL_CACHE_CREATION_TOKENS//[!0-9]/}
TOTAL_CACHE_CREATION_TOKENS=${TOTAL_CACHE_CREATION_TOKENS:-0}
TOTAL_CACHE_READ_TOKENS=${TOTAL_CACHE_READ_TOKENS//[!0-9]/}
TOTAL_CACHE_READ_TOKENS=${TOTAL_CACHE_READ_TOKENS:-0}
MODEL=${MODEL:-unknown}

# --- Guard: skip if no meaningful data extracted (HIGH 2) ---
if [[ "$TOTAL_INPUT_TOKENS" -eq 0 && "$TOTAL_OUTPUT_TOKENS" -eq 0 && "$MODEL" == "unknown" ]]; then
  exit 0
fi

# --- Determine provider from model name ---
PROVIDER="unknown"
if [[ "$MODEL" == claude* ]]; then
  PROVIDER="anthropic"
elif [[ "$MODEL" == gpt* ]]; then
  PROVIDER="openai"
fi

# --- Normalize model name for pricing lookup ---
# Claude model IDs like "claude-opus-4-6-20250929" -> "claude-opus-4-6"
PRICING_MODEL="$MODEL"
PRICING_MODEL=$(echo "$PRICING_MODEL" | sed 's/-[0-9]\{8\}$//')

# --- Look up pricing from budgets.yml ---
# Use python3 for YAML parsing (more reliable than yq which may not be installed)
# Cache token pricing (Anthropic):
#   cache_creation: 1.25x input rate
#   cache_read: 0.10x input rate
#   regular input: 1.00x input rate
# Exact match only -- no partial matching to avoid 43x cost errors
# All variables passed via env vars to prevent code injection
COST_USD="0.0000"
if [[ -f "$BUDGETS_FILE" && "$PROVIDER" != "unknown" ]]; then
  COST_USD=$(
    CFO_BUDGETS_FILE="$BUDGETS_FILE" \
    CFO_PROVIDER="$PROVIDER" \
    CFO_PRICING_MODEL="$PRICING_MODEL" \
    CFO_INPUT_TOKENS="$TOTAL_INPUT_TOKENS" \
    CFO_OUTPUT_TOKENS="$TOTAL_OUTPUT_TOKENS" \
    CFO_CACHE_CREATE_TOKENS="$TOTAL_CACHE_CREATION_TOKENS" \
    CFO_CACHE_READ_TOKENS="$TOTAL_CACHE_READ_TOKENS" \
    python3 -c '
import os, sys
try:
    import yaml
except ImportError:
    print("0.0000")
    print("WARNING: PyYAML not installed, cannot look up pricing", file=sys.stderr)
    sys.exit(0)

with open(os.environ["CFO_BUDGETS_FILE"]) as f:
    config = yaml.safe_load(f) or {}

pricing = config.get("pricing", {})
provider_pricing = pricing.get(os.environ["CFO_PROVIDER"], {})
model_pricing = provider_pricing.get(os.environ["CFO_PRICING_MODEL"], {})

input_rate = float(model_pricing.get("input_per_1m", 0))
output_rate = float(model_pricing.get("output_per_1m", 0))

input_tokens = int(os.environ["CFO_INPUT_TOKENS"])
output_tokens = int(os.environ["CFO_OUTPUT_TOKENS"])
cache_creation_tokens = int(os.environ["CFO_CACHE_CREATE_TOKENS"])
cache_read_tokens = int(os.environ["CFO_CACHE_READ_TOKENS"])

input_cost = input_tokens / 1_000_000 * input_rate
output_cost = output_tokens / 1_000_000 * output_rate
cache_create_cost = cache_creation_tokens / 1_000_000 * input_rate * 1.25
cache_read_cost = cache_read_tokens / 1_000_000 * input_rate * 0.10

cost = input_cost + output_cost + cache_create_cost + cache_read_cost
print(f"{cost:.4f}")
' 2>/dev/null || echo "0.0000")
fi

# --- Detect agent type ---
AGENT="developer"
if grep -q '"code_reviewer"' "$TRANSCRIPT_PATH" 2>/dev/null; then
  AGENT="code_reviewer"
elif grep -q '"scrum_master"' "$TRANSCRIPT_PATH" 2>/dev/null; then
  AGENT="scrum_master"
fi

# --- Detect ticket from git branch ---
TICKET="untracked"
if [[ -d "$CWD/.git" || -f "$CWD/.git" ]]; then
  BRANCH=$(cd "$CWD" && git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
  # Read ticket prefix dynamically from project.conf
  TICKET_PREFIX=""
  if [[ -f "$PROJECT_DIR/.dev-context/project.conf" ]]; then
    TICKET_PREFIX=$(sed -n 's/^LINEAR_TEAM=//p' "$PROJECT_DIR/.dev-context/project.conf" 2>/dev/null || echo "")
  fi
  if [[ -n "$TICKET_PREFIX" && "$BRANCH" =~ (${TICKET_PREFIX}-[0-9]+) ]]; then
    TICKET="${BASH_REMATCH[1]}"
  fi
fi

# --- Generate timestamp ---
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# --- CSV-quote helper (RFC 4180) ---
csv_quote() { printf '"%s"' "${1//\"/\"\"}"; }

# --- Determine billing type and billed amount ---
BILLING_TYPE="${CLAUDE_BILLING_TYPE:-subscription}"
if [[ "$BILLING_TYPE" == "api" ]]; then
  BILLED_USD="$COST_USD"
else
  BILLED_USD="0.0000"
fi

# --- Append to ledger (CRITICAL 2: all string fields quoted per RFC 4180) ---
# 16 columns: ...,ticket,session_start,session_end,duration_sec
# session_start/end empty when transcript carries no timestamps (fail-soft).
echo "$(csv_quote "$TIMESTAMP"),$(csv_quote "$AGENT"),$(csv_quote "$SESSION_ID"),$(csv_quote "$PROVIDER"),$(csv_quote "$MODEL"),$TOTAL_INPUT_TOKENS,$TOTAL_OUTPUT_TOKENS,$TOTAL_CACHE_CREATION_TOKENS,$TOTAL_CACHE_READ_TOKENS,$COST_USD,$(csv_quote "$BILLING_TYPE"),$BILLED_USD,$(csv_quote "$TICKET"),$(csv_quote "$SESSION_START"),$(csv_quote "$SESSION_END"),$DURATION_SEC" >> "$LEDGER_FILE"

exit 0
