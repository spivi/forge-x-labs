#!/usr/bin/env bash
# scripts/budget-analysis.sh
# Analyzes cost-ledger.csv against budgets.yml and proposes tuning.
# Usage: bash scripts/budget-analysis.sh
# Output: Markdown report suitable for human review.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
COST_LEDGER="$PROJECT_DIR/.dev-context/cost-ledger.csv"
BUDGETS="$PROJECT_DIR/.dev-context/budgets.yml"

echo "# Budget Analysis Report"
echo ""
echo "**Generated**: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
echo ""

if [[ ! -f "$COST_LEDGER" ]]; then
  echo "ERROR: cost-ledger.csv not found"; exit 1
fi
if [[ ! -f "$BUDGETS" ]]; then
  echo "ERROR: budgets.yml not found"; exit 1
fi

DATA_ROWS=$(tail -n +2 "$COST_LEDGER" | grep -c .) || DATA_ROWS=0
if [[ "$DATA_ROWS" -eq 0 ]]; then
  echo "No cost data to analyze."; exit 0
fi

# --- Extract budget limits from YAML (simple grep, no yq dependency) ---
DAILY_TOTAL=$(grep -A4 '^\s*daily:' "$BUDGETS" | grep 'total:' | head -1 | awk '{ print $2 }') || DAILY_TOTAL="35.00"
WEEKLY_TOTAL=$(grep -A4 '^\s*weekly:' "$BUDGETS" | grep 'total:' | head -1 | awk '{ print $2 }') || WEEKLY_TOTAL="150.00"
PER_SESSION_MAX=$(grep -A2 '^\s*per_session:' "$BUDGETS" | grep 'max_cost:' | head -1 | awk '{ print $2 }') || PER_SESSION_MAX="10.00"
PER_TICKET_MAX=$(grep -A2 '^\s*per_ticket:' "$BUDGETS" | grep 'max_cost:' | head -1 | awk '{ print $2 }') || PER_TICKET_MAX="30.00"

echo "## Current Budget Limits"
echo ""
echo "| Limit | Value |"
echo "|-------|-------|"
echo "| Daily total | \$${DAILY_TOTAL:-unknown} |"
echo "| Weekly total | \$${WEEKLY_TOTAL:-unknown} |"
echo "| Per-session max | \$${PER_SESSION_MAX:-unknown} |"
echo "| Per-ticket max | \$${PER_TICKET_MAX:-unknown} |"
echo ""

# --- Aggregate actual spend ---
echo "## Actual Spend Analysis"
echo ""
echo "### By Day"
echo ""
echo "| Date | Sessions | Billed Cost | Compute Cost | vs Daily Budget |"
echo "|------|----------|-------------|--------------|----------------|"
awk -F, 'NR>1 {
  gsub(/"/, "", $1); gsub(/"/, "", $10); gsub(/"/, "", $12)
  day = substr($1, 1, 10)
  billed[day] += $12; compute[day] += $10; count[day]++
} END {
  for (d in billed) printf "| %s | %d | $%.4f | $%.4f | %.0f%% |\n", d, count[d], billed[d], compute[d], (billed[d]/'"${DAILY_TOTAL:-35}"')*100
}' "$COST_LEDGER" | sort
echo ""

echo "### By Ticket"
echo ""
echo "| Ticket | Sessions | Billed Cost | vs Per-Ticket Limit |"
echo "|--------|----------|-------------|---------------------|"
awk -F, 'NR>1 {
  gsub(/"/, "", $13); gsub(/"/, "", $12)
  cost[$13] += $12; count[$13]++
} END {
  for (t in cost) printf "| %s | %d | $%.4f | %.0f%% |\n", t, count[t], cost[t], (cost[t]/'"${PER_TICKET_MAX:-30}"')*100
}' "$COST_LEDGER" | sort
echo ""

echo "### By Model"
echo ""
echo "| Model | Sessions | Billed Cost | Avg Billed/Session |"
echo "|-------|----------|-------------|---------------------|"
awk -F, 'NR>1 {
  gsub(/"/, "", $5); gsub(/"/, "", $12)
  cost[$5] += $12; count[$5]++
} END {
  for (m in cost) printf "| %s | %d | $%.4f | $%.4f |\n", m, count[m], cost[m], cost[m]/count[m]
}' "$COST_LEDGER" | sort
echo ""

# --- Data quality check ---
echo "## Data Quality Check"
echo ""
echo "Cross-referencing token counts against pricing to detect anomalies."
echo ""

# Check if compute_cost_usd seems reasonable vs token counts (including cache)
# Opus pricing: $15/1M input, $75/1M output, cache_create=1.25x input, cache_read=0.1x input
awk -F, 'NR>1 {
  gsub(/"/, "", $6); gsub(/"/, "", $7); gsub(/"/, "", $8); gsub(/"/, "", $9); gsub(/"/, "", $10)
  input_tokens = $6 + 0
  output_tokens = $7 + 0
  cache_create = $8 + 0
  cache_read = $9 + 0
  reported_cost = $10 + 0
  estimated = (input_tokens * 15 / 1000000) + (output_tokens * 75 / 1000000) + (cache_create * 15 * 1.25 / 1000000) + (cache_read * 15 * 0.10 / 1000000)
  ratio = (estimated > 0) ? reported_cost / estimated : 0
  if (ratio > 5 || ratio < 0.1) {
    gsub(/"/, "", $1); gsub(/"/, "", $3)
    printf "ANOMALY: Session %s (%s) — compute $%.2f vs estimated $%.2f (%.0fx)\n", $3, $1, reported_cost, estimated, ratio
  }
}' "$COST_LEDGER"

ANOMALY_COUNT=$(awk -F, 'NR>1 {
  gsub(/"/, "", $6); gsub(/"/, "", $7); gsub(/"/, "", $8); gsub(/"/, "", $9); gsub(/"/, "", $10)
  est = ($6 * 15 / 1000000) + ($7 * 75 / 1000000) + ($8 * 15 * 1.25 / 1000000) + ($9 * 15 * 0.10 / 1000000)
  ratio = (est > 0) ? $10 / est : 0
  if (ratio > 5 || ratio < 0.1) count++
} END { print count+0 }' "$COST_LEDGER")

if [[ "$ANOMALY_COUNT" -gt 0 ]]; then
  echo ""
  echo "WARNING: $ANOMALY_COUNT session(s) have cost values that diverge >5x"
  echo "from expected cost based on token counts and Opus pricing."
  echo "The cost calculation in log-session-cost.sh may need review."
  echo "Possible causes: cache token pricing applied incorrectly, or"
  echo "cost field includes cumulative session cost rather than per-turn cost."
else
  echo "No anomalies detected. Costs align with token-based estimates."
fi
echo ""

# --- Tuning proposal ---
TOTAL_COST=$(awk -F, 'NR>1 { gsub(/"/, "", $12); sum += $12 } END { printf "%.2f", sum }' "$COST_LEDGER")
TOTAL_SESSIONS=$DATA_ROWS
AVG_SESSION=$(awk "BEGIN { printf \"%.2f\", $TOTAL_COST / $TOTAL_SESSIONS }")

echo "## Tuning Proposal"
echo ""
echo "Based on $TOTAL_SESSIONS sessions totaling \$$TOTAL_COST:"
echo ""
echo "- **Avg cost per session**: \$$AVG_SESSION"
echo "- **Data quality**: Review anomalies above before adjusting budgets"
echo ""
echo "### Recommendations"
echo ""
if [[ "$ANOMALY_COUNT" -gt 0 ]]; then
  echo "1. **Fix cost calculation first** — anomalous cost values make budget"
  echo "   tuning unreliable. Investigate log-session-cost.sh before adjusting."
  echo "2. Once costs are accurate, re-run this analysis for valid proposals."
else
  echo "1. Current daily budget of \$${DAILY_TOTAL:-35} appears adequate"
  echo "2. Consider per-ticket budgets based on actual ticket costs above"
  echo "3. Review model usage — cheaper models for non-critical tasks save cost"
fi
