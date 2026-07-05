#!/usr/bin/env bash
# scripts/kpi-summary.sh
# Reads all KPI CSV ledgers and outputs a formatted summary for sprint retrospectives.
# Usage: bash scripts/kpi-summary.sh
# No external dependencies — uses only awk and standard shell tools.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
KPI_DIR="$PROJECT_DIR/.dev-context/kpis"
COST_LEDGER="$PROJECT_DIR/.dev-context/cost-ledger.csv"

echo "=================================="
echo " KPI Summary Report"
echo " Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
echo "=================================="
echo ""

# --- Cost Ledger ---
echo "## Cost Governance (Budget Review)"
echo ""
if [[ -f "$COST_LEDGER" ]]; then
  DATA_ROWS=$(tail -n +2 "$COST_LEDGER" | grep -c .) || DATA_ROWS=0
  if [[ "$DATA_ROWS" -gt 0 ]]; then
    TOTAL_BILLED=$(awk -F, 'NR>1 { gsub(/"/, "", $12); if ($12 != "") sum += $12 } END { printf "%.4f", sum }' "$COST_LEDGER")
    TOTAL_COMPUTE=$(awk -F, 'NR>1 { gsub(/"/, "", $10); if ($10 != "") sum += $10 } END { printf "%.4f", sum }' "$COST_LEDGER")
    UNIQUE_TICKETS=$(awk -F, 'NR>1 { gsub(/"/, "", $13); if ($13 != "" && $13 != "untracked") print $13 }' "$COST_LEDGER" | sort -u | wc -l | tr -d ' ')
    UNIQUE_SESSIONS=$(awk -F, 'NR>1 { gsub(/"/, "", $3); print $3 }' "$COST_LEDGER" | sort -u | wc -l | tr -d ' ')
    echo "  Sessions: $UNIQUE_SESSIONS"
    echo "  Total billed: \$$TOTAL_BILLED"
    echo "  Total compute: \$$TOTAL_COMPUTE"
    echo "  Tracked tickets: $UNIQUE_TICKETS"
    echo "  Untracked sessions: $(awk -F, 'NR>1 { gsub(/"/, "", $13); if ($13 == "untracked") count++ } END { print count+0 }' "$COST_LEDGER")"
    echo ""
    echo "  Per-ticket breakdown:"
    awk -F, 'NR>1 && $13 != "" {
      gsub(/"/, "", $13); gsub(/"/, "", $12)
      cost[$13] += $12; count[$13]++
    } END {
      for (t in cost) printf "    %-15s %d session(s)  $%.4f\n", t, count[t], cost[t]
    }' "$COST_LEDGER" | sort
  else
    echo "  No cost data recorded yet."
  fi
else
  echo "  cost-ledger.csv not found."
fi
echo ""

# --- Sprint Log ---
echo "## Sprint Metrics (Scrum Master)"
echo ""
if [[ -f "$KPI_DIR/sprint-log.csv" ]]; then
  DATA_ROWS=$(tail -n +2 "$KPI_DIR/sprint-log.csv" | grep -c .) || DATA_ROWS=0
  if [[ "$DATA_ROWS" -gt 0 ]]; then
    LAST_SPRINT=$(tail -1 "$KPI_DIR/sprint-log.csv")
    echo "  Last sprint: $(echo "$LAST_SPRINT" | awk -F, '{ print $1 }')"
    echo "  Planned/Completed: $(echo "$LAST_SPRINT" | awk -F, '{ print $4 "/" $5 }')"
    echo "  Conflicts: $(echo "$LAST_SPRINT" | awk -F, '{ print $6 }')"
    echo "  Avg cycle hours: $(echo "$LAST_SPRINT" | awk -F, '{ print $7 }')"
  else
    echo "  No sprint data recorded yet."
  fi
else
  echo "  sprint-log.csv not found."
fi
echo ""

# --- Review Log ---
echo "## Code Review Metrics"
echo ""
if [[ -f "$KPI_DIR/review-log.csv" ]]; then
  DATA_ROWS=$(tail -n +2 "$KPI_DIR/review-log.csv" | grep -c .) || DATA_ROWS=0
  if [[ "$DATA_ROWS" -gt 0 ]]; then
    TOTAL_REVIEWS=$(awk -F, 'NR>1 { count++ } END { print count+0 }' "$KPI_DIR/review-log.csv")
    AVG_TURNAROUND=$(awk -F, 'NR>1 && $6 != "" { sum+=$6; count++ } END { if(count>0) printf "%.1f", sum/count; else print "N/A" }' "$KPI_DIR/review-log.csv")
    FALSE_POS=$(awk -F, 'NR>1 { sum+=$5 } END { print sum+0 }' "$KPI_DIR/review-log.csv")
    echo "  Total reviews: $TOTAL_REVIEWS"
    echo "  Avg turnaround: ${AVG_TURNAROUND} min"
    echo "  Total false positives: $FALSE_POS"
  else
    echo "  No review data recorded yet."
  fi
else
  echo "  review-log.csv not found."
fi
echo ""

# --- Bug Ledger ---
echo "## Bug Traceability (Developer Worker)"
echo ""
if [[ -f "$KPI_DIR/bug-ledger.csv" ]]; then
  DATA_ROWS=$(tail -n +2 "$KPI_DIR/bug-ledger.csv" | grep -c .) || DATA_ROWS=0
  if [[ "$DATA_ROWS" -gt 0 ]]; then
    TOTAL_BUGS=$DATA_ROWS
    RETRO_DONE=$(awk -F, 'NR>1 && $9 == "true" { count++ } END { print count+0 }' "$KPI_DIR/bug-ledger.csv")
    echo "  Total bugs: $TOTAL_BUGS"
    echo "  Retrospectives done: $RETRO_DONE / $TOTAL_BUGS"
    echo "  Category distribution:"
    awk -F, 'NR>1 && $8 != "" { gsub(/"/, "", $8); cat[$8]++ } END {
      for (c in cat) printf "    %-25s %d\n", c, cat[c]
    }' "$KPI_DIR/bug-ledger.csv" | sort
  else
    echo "  No bugs recorded (target: 0 bugs/feature)."
  fi
else
  echo "  bug-ledger.csv not found."
fi
echo ""

# --- Release Log ---
echo "## Release Metrics (Handoff Manager)"
echo ""
if [[ -f "$KPI_DIR/release-log.csv" ]]; then
  DATA_ROWS=$(tail -n +2 "$KPI_DIR/release-log.csv" | grep -c .) || DATA_ROWS=0
  if [[ "$DATA_ROWS" -gt 0 ]]; then
    TOTAL_RELEASES=$DATA_ROWS
    LAST_RELEASE=$(tail -1 "$KPI_DIR/release-log.csv" | awk -F, '{ print $1 " (" $2 ")" }')
    FIRST_DRAFT_OK=$(awk -F, 'NR>1 && $5 == "true" { count++ } END { print count+0 }' "$KPI_DIR/release-log.csv")
    echo "  Total releases: $TOTAL_RELEASES"
    echo "  Last release: $LAST_RELEASE"
    echo "  First-draft approval rate: $FIRST_DRAFT_OK / $TOTAL_RELEASES"
  else
    echo "  No releases recorded yet."
  fi
else
  echo "  release-log.csv not found."
fi
echo ""

# --- Security Audit Log ---
echo "## Security Metrics (Security Architect)"
echo ""
if [[ -f "$KPI_DIR/security-audit-log.csv" ]]; then
  DATA_ROWS=$(tail -n +2 "$KPI_DIR/security-audit-log.csv" | grep -c .) || DATA_ROWS=0
  if [[ "$DATA_ROWS" -gt 0 ]]; then
    TOTAL_AUDITS=$DATA_ROWS
    CRITICAL_FINDINGS=$(awk -F, 'NR>1 { sum+=$6 } END { print sum+0 }' "$KPI_DIR/security-audit-log.csv")
    echo "  Total audits: $TOTAL_AUDITS"
    echo "  Critical findings: $CRITICAL_FINDINGS"
  else
    echo "  No security audit data recorded yet."
  fi
else
  echo "  security-audit-log.csv not found."
fi
echo ""

# --- E2E Test Log ---
echo "## E2E Testing Metrics"
echo ""
if [[ -f "$KPI_DIR/e2e-test-log.csv" ]]; then
  DATA_ROWS=$(tail -n +2 "$KPI_DIR/e2e-test-log.csv" | grep -c .) || DATA_ROWS=0
  if [[ "$DATA_ROWS" -gt 0 ]]; then
    TOTAL_RUNS=$DATA_ROWS
    PASS_RATE=$(awk -F, 'NR>1 && $11 ~ /pass/ { count++ } END { if(NR>1) printf "%.0f%%", count*100/(NR-1); else print "N/A" }' "$KPI_DIR/e2e-test-log.csv")
    echo "  Total test runs: $TOTAL_RUNS"
    echo "  Pass rate: $PASS_RATE"
  else
    echo "  No E2E test data recorded yet."
  fi
else
  echo "  e2e-test-log.csv not found."
fi
echo ""

echo "=================================="
echo " End of KPI Summary"
echo "=================================="
