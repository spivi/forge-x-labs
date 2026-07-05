#!/usr/bin/env bash
# .claude/hooks/sync-context.sh
# Claude Code SessionStart hook: loads project context for every session
#
# Input: JSON on stdin with session_id, source, cwd, model
# Output: Context summary printed to stdout (injected into Claude session)
#
# Required tools: none (jq optional for parsing session source)
# Performance target: <5 seconds

set -euo pipefail

# --- Configuration ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$SCRIPT_DIR/../.." && pwd)}"

# --- Read hook input from stdin ---
INPUT=$(cat)

# --- Guard: ensure project dir exists ---
if [[ ! -d "$PROJECT_DIR" ]]; then
  exit 0
fi

# --- File paths ---
STATUS_FILE="$PROJECT_DIR/STATUS.md"
BACKLOG_FILE="$PROJECT_DIR/BACKLOG.md"
DECISIONS_FILE="$PROJECT_DIR/.dev-context/DECISIONS.md"
PROJECT_CONF="$PROJECT_DIR/.dev-context/project.conf"
INBOX_DIR="$PROJECT_DIR/.dev-context/inbox"

# --- Parse session source (jq optional) ---
SOURCE="startup"
if command -v jq >/dev/null 2>&1; then
  SOURCE=$(echo "$INPUT" | jq -r '.source // "startup"' 2>/dev/null || echo "startup")
fi

# --- Project identity ---
PROJECT_ID="TPL"
PROJECT_NAME="unknown"
if [[ -f "$PROJECT_CONF" ]]; then
  PROJECT_ID=$(sed -n 's/^PROJECT_ID=//p' "$PROJECT_CONF" 2>/dev/null || echo "TPL")
  PROJECT_NAME=$(sed -n 's/^PROJECT_NAME=//p' "$PROJECT_CONF" 2>/dev/null || echo "unknown")
fi

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# --- Build context output ---
OUTPUT=""

# --- Header ---
OUTPUT+="# Session Context — ${PROJECT_ID} (${PROJECT_NAME})"$'\n'
OUTPUT+="Generated: ${TIMESTAMP}"$'\n'
OUTPUT+=""$'\n'

# --- Source-specific note (compact/resume) ---
if [[ "$SOURCE" == "compact" ]]; then
  OUTPUT+="NOTE: Context was compacted. This is a full context refresh. Re-read .claude/cc10x/activeContext.md for session memory."$'\n'
  OUTPUT+=""$'\n'
elif [[ "$SOURCE" == "resume" ]]; then
  OUTPUT+="NOTE: Session resumed. Verify current state matches expectations."$'\n'
  OUTPUT+=""$'\n'
fi

# --- Inbox summary (critical first per config) ---
if [[ -d "$INBOX_DIR" ]]; then
  CRITICAL_COUNT=0
  APPROVAL_COUNT=0
  DIGEST_COUNT=0

  if [[ -d "$INBOX_DIR/critical" ]]; then
    CRITICAL_COUNT=$(find "$INBOX_DIR/critical" -name "*.md" -type f 2>/dev/null | wc -l | tr -d ' ')
  fi
  if [[ -d "$INBOX_DIR/approval" ]]; then
    APPROVAL_COUNT=$(find "$INBOX_DIR/approval" -name "*.md" -type f 2>/dev/null | wc -l | tr -d ' ')
  fi
  if [[ -d "$INBOX_DIR/digest" ]]; then
    DIGEST_COUNT=$(find "$INBOX_DIR/digest" -name "*.md" -type f 2>/dev/null | wc -l | tr -d ' ')
  fi

  if [[ $CRITICAL_COUNT -gt 0 || $APPROVAL_COUNT -gt 0 || $DIGEST_COUNT -gt 0 ]]; then
    OUTPUT+="### Inbox"$'\n'

    if [[ $CRITICAL_COUNT -gt 0 ]]; then
      PENDING_CRIT=0
      CRIT_ITEMS=""
      for f in "$INBOX_DIR/critical/"*.md; do
        [[ -f "$f" ]] || continue
        STATUS_LINE=$(grep -m1 '^\*\*Status\*\*:' "$f" 2>/dev/null || echo "")
        case "$STATUS_LINE" in *APPROVED*|*REJECTED*|*ACKNOWLEDGED*) continue ;; esac
        TITLE=$(head -1 "$f" | sed 's/^# //')
        FROM=$(grep -m1 '^\*\*From\*\*:' "$f" 2>/dev/null | sed 's/\*\*From\*\*: //' || echo "unknown")
        CRIT_ITEMS+="  - ${FROM}: ${TITLE}"$'\n'
        PENDING_CRIT=$((PENDING_CRIT + 1))
      done
      if [[ $PENDING_CRIT -gt 0 ]]; then
        OUTPUT+="CRITICAL: ${PENDING_CRIT} item(s) requiring immediate attention"$'\n'
        OUTPUT+="${CRIT_ITEMS}"
      fi
    fi

    if [[ $APPROVAL_COUNT -gt 0 ]]; then
      PENDING_APPR=0
      APPR_ITEMS=""
      for f in "$INBOX_DIR/approval/"*.md; do
        [[ -f "$f" ]] || continue
        STATUS_LINE=$(grep -m1 '^\*\*Status\*\*:' "$f" 2>/dev/null || echo "")
        case "$STATUS_LINE" in *APPROVED*|*REJECTED*|*ACKNOWLEDGED*) continue ;; esac
        TITLE=$(head -1 "$f" | sed 's/^# //')
        FROM=$(grep -m1 '^\*\*From\*\*:' "$f" 2>/dev/null | sed 's/\*\*From\*\*: //' || echo "unknown")
        APPR_ITEMS+="  - ${FROM}: ${TITLE}"$'\n'
        PENDING_APPR=$((PENDING_APPR + 1))
      done
      if [[ $PENDING_APPR -gt 0 ]]; then
        OUTPUT+="APPROVAL: ${PENDING_APPR} item(s) awaiting your decision"$'\n'
        OUTPUT+="${APPR_ITEMS}"
      fi
    fi

    if [[ $DIGEST_COUNT -gt 0 ]]; then
      OUTPUT+="INFO: ${DIGEST_COUNT} unread digest(s)"$'\n'
    fi

    OUTPUT+=""$'\n'
  fi
fi

# --- Current status from STATUS.md ---
if [[ -f "$STATUS_FILE" ]]; then
  OUTPUT+="## Current Status"$'\n'

  PHASE_LINE=$(grep -m1 "Current Phase" "$STATUS_FILE" 2>/dev/null || echo "")
  if [[ -n "$PHASE_LINE" ]]; then
    OUTPUT+="${PHASE_LINE}"$'\n'
  fi

  UPDATED_LINE=$(grep -m1 "Last Updated" "$STATUS_FILE" 2>/dev/null || echo "")
  if [[ -n "$UPDATED_LINE" ]]; then
    OUTPUT+="${UPDATED_LINE}"$'\n'
  fi

  OUTPUT+=""$'\n'

  # Next Steps section (up to 5 lines after header)
  NEXT_STEPS=$(sed -n '/^### Next Steps$/,/^##/{
    /^### Next Steps$/d
    /^##/d
    p
  }' "$STATUS_FILE" 2>/dev/null | head -5)
  if [[ -n "$NEXT_STEPS" ]]; then
    OUTPUT+="### Next Steps"$'\n'
    OUTPUT+="${NEXT_STEPS}"$'\n'
    OUTPUT+=""$'\n'
  fi

  # Active Worktrees table
  WORKTREES=$(sed -n '/^## Active Worktrees$/,/^##/{
    /^## Active Worktrees$/d
    /^##/d
    p
  }' "$STATUS_FILE" 2>/dev/null | head -10)
  if [[ -n "$WORKTREES" ]]; then
    OUTPUT+="### Active Worktrees"$'\n'
    OUTPUT+="${WORKTREES}"$'\n'
    OUTPUT+=""$'\n'
  fi

  # Agent Pipeline Status
  AGENT_TABLE=$(sed -n '/^## Agent Pipeline Status$/,/^##/{
    /^## Agent Pipeline Status$/d
    /^##/d
    p
  }' "$STATUS_FILE" 2>/dev/null | head -15)
  if [[ -n "$AGENT_TABLE" ]]; then
    OUTPUT+="### Agent Pipeline"$'\n'
    OUTPUT+="${AGENT_TABLE}"$'\n'
    OUTPUT+=""$'\n'
  fi
else
  OUTPUT+="## Current Status"$'\n'
  OUTPUT+="WARNING: STATUS.md not found"$'\n'
  OUTPUT+=""$'\n'
fi

# --- Top Backlog Items (up to 5) ---
if [[ -f "$BACKLOG_FILE" ]]; then
  TOP_TICKETS=$(grep -m5 "^\- \[ \] \*\*${PROJECT_ID}-" "$BACKLOG_FILE" 2>/dev/null || echo "")
  if [[ -n "$TOP_TICKETS" ]]; then
    OUTPUT+="### Top Backlog Items"$'\n'
    OUTPUT+="${TOP_TICKETS}"$'\n'
    OUTPUT+=""$'\n'
  fi
fi

# --- Key Decisions (last 5) ---
if [[ -f "$DECISIONS_FILE" ]]; then
  DECISIONS=$(grep "^## ${PROJECT_ID}-D" "$DECISIONS_FILE" 2>/dev/null | tail -5 || echo "")
  if [[ -n "$DECISIONS" ]]; then
    OUTPUT+="### Key Decisions"$'\n'
    OUTPUT+="${DECISIONS}"$'\n'
    OUTPUT+=""$'\n'
  fi
fi

# --- cc10x session memory (surface so it is actually read) ---
# Fail-soft and quiet on a fresh project: placeholder lines (`_(...)_`) and the
# empty patterns template produce no output.
CC10X_DIR="$PROJECT_DIR/.claude/cc10x"
if [[ -d "$CC10X_DIR" ]]; then
  if [[ -f "$CC10X_DIR/activeContext.md" ]]; then
    FOCUS=$(awk '/^## Current Focus$/{f=1;next} /^## /{f=0} f' "$CC10X_DIR/activeContext.md" 2>/dev/null \
      | grep '^- ' | grep -v '_(' | head -5 || true)
    if [[ -n "$FOCUS" ]]; then
      OUTPUT+="### cc10x — Current Focus"$'\n'
      OUTPUT+="${FOCUS}"$'\n'
      OUTPUT+=""$'\n'
    fi
  fi
  if [[ -f "$CC10X_DIR/patterns.md" ]]; then
    PCOUNT=$(grep -cE '^- ' "$CC10X_DIR/patterns.md" 2>/dev/null || echo 0)
    if [[ "${PCOUNT:-0}" -gt 0 ]]; then
      OUTPUT+="### cc10x — Patterns (${PCOUNT} known gotchas)"$'\n'
      OUTPUT+="Read .claude/cc10x/patterns.md before implementing — do not relearn known traps."$'\n'
      OUTPUT+=""$'\n'
    fi
  fi
fi

# --- Drift Detection ---
DRIFT_WARNING=""
STALENESS_THRESHOLD=14400  # 4 hours in seconds
for snapshot_file in "$PROJECT_DIR/.dev-context/web-context.md" "$PROJECT_DIR/.dev-context/mobile-context.md" "$PROJECT_DIR/.dev-context/api-context.json"; do
  if [[ -f "$snapshot_file" ]]; then
    FILE_MOD=$(stat -f %m "$snapshot_file" 2>/dev/null || stat -c %Y "$snapshot_file" 2>/dev/null || echo "0")
    NOW=$(date +%s)
    AGE=$((NOW - FILE_MOD))
    if [[ $AGE -gt $STALENESS_THRESHOLD ]]; then
      BASENAME=$(basename "$snapshot_file")
      HOURS=$((AGE / 3600))
      DRIFT_WARNING+="WARNING: ${BASENAME} was ${HOURS}h stale (regenerating now)"$'\n'
    fi
  fi
done

if [[ -n "$DRIFT_WARNING" ]]; then
  OUTPUT="${DRIFT_WARNING}${OUTPUT}"
fi

# --- Generate surface-specific snapshots ---
generate_snapshots() {
  local dev_context="$PROJECT_DIR/.dev-context"
  [[ -d "$dev_context" ]] || return 0

  # --- Web Context (compact) ---
  local web_file="$dev_context/web-context.md"
  {
    echo "# Web Session Context — ${PROJECT_ID} (${PROJECT_NAME})"
    echo "Last synced: ${TIMESTAMP}"
    echo ""
    echo "## Your Role"
    echo "You are an advisor for the ${PROJECT_ID} project. Read-only mode — focus on"
    echo "code review, planning, Q&A, and architectural guidance."
    echo "Use conventional commits. Follow rules in .dev-context/rules/."
    echo ""

    if [[ -f "$STATUS_FILE" ]]; then
      echo "## Current Status"
      grep -m1 "Current Phase" "$STATUS_FILE" 2>/dev/null || true
      grep -m1 "Last Updated" "$STATUS_FILE" 2>/dev/null || true
      echo ""

      local steps
      steps=$(sed -n '/^### Next Steps$/,/^##/{
        /^### Next Steps$/d
        /^##/d
        p
      }' "$STATUS_FILE" 2>/dev/null | head -5)
      if [[ -n "$steps" ]]; then
        echo "### Next Steps"
        echo "$steps"
        echo ""
      fi
    fi

    if [[ -f "$BACKLOG_FILE" ]]; then
      local tickets
      tickets=$(grep -m5 "^\- \[ \] \*\*${PROJECT_ID}-" "$BACKLOG_FILE" 2>/dev/null || true)
      if [[ -n "$tickets" ]]; then
        echo "## Top Backlog Items"
        echo "$tickets"
        echo ""
      fi
    fi

    if [[ -f "$DECISIONS_FILE" ]]; then
      local decisions
      decisions=$(grep "^## ${PROJECT_ID}-D" "$DECISIONS_FILE" 2>/dev/null | tail -5 || true)
      if [[ -n "$decisions" ]]; then
        echo "## Active Decisions"
        echo "$decisions"
        echo ""
      fi
    fi
  } > "$web_file"

  # --- Mobile Context (ultra-compact) ---
  local mobile_file="$dev_context/mobile-context.md"
  {
    echo "# Mobile Context — ${PROJECT_ID}"
    echo "Last synced: ${TIMESTAMP}"
    echo ""
    echo "Role: Quick advisor and approver. Focus on decisions, approvals, and blockers."
    echo ""

    if [[ -f "$STATUS_FILE" ]]; then
      grep -m1 "Current Phase" "$STATUS_FILE" 2>/dev/null || true
      echo ""

      local blockers
      blockers=$(sed -n '/^## Known Issues$/,/^##/{
        /^## Known Issues$/d
        /^##/d
        p
      }' "$STATUS_FILE" 2>/dev/null | head -3)
      if [[ -n "$blockers" ]]; then
        echo "## Blockers"
        echo "$blockers"
        echo ""
      fi
    fi

    if [[ -f "$BACKLOG_FILE" ]]; then
      local tickets
      tickets=$(grep -m3 "^\- \[ \] \*\*${PROJECT_ID}-" "$BACKLOG_FILE" 2>/dev/null || true)
      if [[ -n "$tickets" ]]; then
        echo "## Top 3 Priorities"
        echo "$tickets"
        echo ""
      fi
    fi

    if [[ -d "$INBOX_DIR" ]]; then
      local crit appr
      crit=$(find "$INBOX_DIR/critical" -name "*.md" -type f 2>/dev/null | wc -l | tr -d ' ')
      appr=$(find "$INBOX_DIR/approval" -name "*.md" -type f 2>/dev/null | wc -l | tr -d ' ')
      if [[ ${crit:-0} -gt 0 || ${appr:-0} -gt 0 ]]; then
        echo "## Inbox"
        [[ ${crit:-0} -gt 0 ]] && echo "CRITICAL: $crit"
        [[ ${appr:-0} -gt 0 ]] && echo "Awaiting approval: $appr"
        echo ""
      fi
    fi
  } > "$mobile_file"

  # --- API Context (JSON) ---
  local api_file="$dev_context/api-context.json"

  local current_phase=""
  local last_updated=""
  if [[ -f "$STATUS_FILE" ]]; then
    current_phase=$(grep -m1 "Current Phase" "$STATUS_FILE" 2>/dev/null | sed 's/.*\*\*Current Phase:\*\* //' || echo "unknown")
    last_updated=$(grep -m1 "Last Updated" "$STATUS_FILE" 2>/dev/null | sed 's/.*\*\*Last Updated:\*\* //' || echo "unknown")
  fi

  local crit_count=0 appr_count=0 digest_count=0
  if [[ -d "$INBOX_DIR" ]]; then
    crit_count=$(find "$INBOX_DIR/critical" -name "*.md" -type f 2>/dev/null | wc -l | tr -d ' ')
    appr_count=$(find "$INBOX_DIR/approval" -name "*.md" -type f 2>/dev/null | wc -l | tr -d ' ')
    digest_count=$(find "$INBOX_DIR/digest" -name "*.md" -type f 2>/dev/null | wc -l | tr -d ' ')
  fi

  local ticket_ids="[]"
  if [[ -f "$BACKLOG_FILE" ]]; then
    ticket_ids=$(grep -o "${PROJECT_ID}-[0-9][0-9]*" "$BACKLOG_FILE" 2>/dev/null | awk '!seen[$0]++' | head -5 | python3 -c "
import sys, json
ids = [line.strip() for line in sys.stdin if line.strip()]
print(json.dumps(ids))
" 2>/dev/null || echo "[]")
  fi

  API_PROJECT_ID="$PROJECT_ID" \
  API_PROJECT_NAME="$PROJECT_NAME" \
  API_TIMESTAMP="$TIMESTAMP" \
  API_PHASE="$current_phase" \
  API_LAST_UPDATED="$last_updated" \
  API_CRIT="${crit_count:-0}" \
  API_APPR="${appr_count:-0}" \
  API_DIGEST="${digest_count:-0}" \
  API_TICKETS="$ticket_ids" \
  python3 -c '
import os, json
data = {
    "project_id": os.environ["API_PROJECT_ID"],
    "project_name": os.environ["API_PROJECT_NAME"],
    "last_synced": os.environ["API_TIMESTAMP"],
    "current_phase": os.environ["API_PHASE"],
    "status_last_updated": os.environ["API_LAST_UPDATED"],
    "inbox": {
        "critical": int(os.environ["API_CRIT"]),
        "approval": int(os.environ["API_APPR"]),
        "digest": int(os.environ["API_DIGEST"])
    },
    "top_backlog_tickets": json.loads(os.environ["API_TICKETS"]),
    "role": "Worker Agent — configurable per invocation"
}
print(json.dumps(data, indent=2))
' > "$api_file" 2>/dev/null || echo '{"error": "failed to generate api-context.json"}' > "$api_file"
}

# Always regenerate snapshots on session start
generate_snapshots

# Print output to stdout (Claude Code injects this as session context)
echo "$OUTPUT"

exit 0
