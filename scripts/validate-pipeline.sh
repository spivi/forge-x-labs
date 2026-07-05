#!/usr/bin/env bash
# scripts/validate-pipeline.sh
# Validates that all pipeline stages have prerequisites met.
# Usage: bash scripts/validate-pipeline.sh
# Output: Structured report with PASS/WARN/FAIL per stage.
#
# NOTE: This is a template. Project-specific checks (e.g., specific agent
# specs, app-specific workflows) use check_warn() instead of check() so
# they produce warnings rather than hard failures. Customize as needed.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DC="$PROJECT_DIR/.dev-context"

PASS=0; WARN=0; FAIL=0; TOTAL=0
DETAILS=""

check() {
  local label="$1" condition="$2"
  TOTAL=$((TOTAL + 1))
  if eval "$condition" >/dev/null 2>&1; then
    PASS=$((PASS + 1))
  else
    DETAILS+="    - FAIL: $label"$'\n'
    FAIL=$((FAIL + 1))
  fi
}

check_warn() {
  local label="$1" condition="$2"
  TOTAL=$((TOTAL + 1))
  if eval "$condition" >/dev/null 2>&1; then
    PASS=$((PASS + 1))
  else
    DETAILS+="    - WARN: $label"$'\n'
    WARN=$((WARN + 1))
  fi
}

stage() {
  local num="$1" name="$2"
  STAGE_PASS=$PASS; STAGE_WARN=$WARN; STAGE_FAIL=$FAIL; STAGE_TOTAL=$TOTAL
  DETAILS=""
}

report_stage() {
  local num="$1" name="$2"
  local s_checks=$((TOTAL - STAGE_TOTAL))
  local s_pass=$((PASS - STAGE_PASS))
  local s_fail=$((FAIL - STAGE_FAIL))
  local s_warn=$((WARN - STAGE_WARN))
  local verdict="PASS"
  [[ $s_warn -gt 0 ]] && verdict="WARN"
  [[ $s_fail -gt 0 ]] && verdict="FAIL"
  echo "  [$verdict] Stage $num: $name -- $s_pass/$s_checks checks"
  if [[ -n "$DETAILS" ]]; then printf "%s" "$DETAILS"; fi
}

echo "=================================="
echo " Pipeline Validation Report"
echo " $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
echo "=================================="
echo ""

# --- Stage 1: Idea Intake (PM Agent) ---
stage 1 "Idea Intake"
check_warn "PM spec exists" "[[ -f '$DC/agents/product_manager.md' ]]"
check_warn "/prd skill exists" "[[ -f '$DC/skills/prd/SKILL.md' ]]"
check_warn "prds/ directory exists" "[[ -d '$DC/prds' ]]"
check_warn "gh CLI authenticated" "gh auth status"
report_stage 1 "Idea Intake (PM Agent)"

# --- Stage 2: Backlog Management (Scrum Master) ---
stage 2 "Backlog Management"
check_warn "SM spec exists" "[[ -f '$DC/agents/scrum_master.md' ]]"
check_warn "/sprint skill exists" "[[ -f '$DC/skills/sprint/SKILL.md' ]]"
check "budgets.yml exists" "[[ -f '$DC/budgets.yml' ]]"
check "cost-ledger.csv exists" "[[ -f '$DC/cost-ledger.csv' ]]"
report_stage 2 "Backlog Management (Scrum Master)"

# --- Stage 3: Development (Developer Worker) ---
stage 3 "Development"
check_warn "Developer spec exists" "[[ -f '$DC/agents/developer.md' ]]"
check ".venv exists" "[[ -d '$PROJECT_DIR/.venv' ]]"
check_warn "pre-commit installed" "command -v pre-commit"
check_warn "ruff installed" "$PROJECT_DIR/.venv/bin/python -c 'import ruff' 2>/dev/null || command -v ruff"
report_stage 3 "Development (Developer Worker)"

# --- Stage 4: Code Review ---
stage 4 "Code Review"
check_warn "ai-code-review.yml exists" "[[ -f '$PROJECT_DIR/.github/workflows/ai-code-review.yml' ]]"
check_warn "ai-security-review.yml exists" "[[ -f '$PROJECT_DIR/.github/workflows/ai-security-review.yml' ]]"
check_warn "dependency-audit.yml exists" "[[ -f '$PROJECT_DIR/.github/workflows/dependency-audit.yml' ]]"
check_warn "Code Reviewer spec exists" "[[ -f '$DC/agents/code_reviewer.md' ]]"
check_warn "Security Architect spec exists" "[[ -f '$DC/agents/security_architect.md' ]]"
report_stage 4 "Code Review (Reviewer + Security)"

# --- Stage 5: E2E Testing ---
stage 5 "E2E Testing"
check_warn "e2e-tests.yml exists" "[[ -f '$PROJECT_DIR/.github/workflows/e2e-tests.yml' ]]"
check_warn "E2E Tester spec exists" "[[ -f '$DC/agents/e2e_tester.md' ]]"
check "tests/ directory exists" "[[ -d '$PROJECT_DIR/tests' ]]"
report_stage 5 "E2E Testing"

# --- Stage 6: Release Management ---
stage 6 "Release Management"
check_warn "release.yml exists" "[[ -f '$PROJECT_DIR/.github/workflows/release.yml' ]]"
check_warn "/release skill exists" "[[ -f '$DC/skills/release/SKILL.md' ]]"
check_warn "Handoff Manager spec exists" "[[ -f '$DC/agents/handoff_manager.md' ]]"
check_warn "git tag exists" "git -C '$PROJECT_DIR' describe --tags --abbrev=0"
check_warn "release-log.csv exists" "[[ -f '$DC/kpis/release-log.csv' ]]"
report_stage 6 "Release Management (Handoff Manager)"

# --- Stage 7: Cost Governance ---
stage 7 "Cost Governance"
check_warn "Budget Review spec exists" "[[ -f '$DC/agents/budget_review.md' ]]"
check_warn "budgets.yml has thresholds" "grep -q 'circuit_break_at' '$DC/budgets.yml'"
check_warn "cost-ledger.csv has data" "[[ \$(tail -n +2 '$DC/cost-ledger.csv' | grep -c .) -gt 0 ]]"
check_warn "log-session-cost.sh exists" "[[ -f '$PROJECT_DIR/.claude/hooks/log-session-cost.sh' ]]"
report_stage 7 "Cost Governance (Budget Review)"

# --- Stage 8: Learning Loop ---
stage 8 "Learning Loop"
check "estimator.py exists" "[[ -f '$PROJECT_DIR/scripts/estimator.py' ]]"
check "tracker.py exists" "[[ -f '$PROJECT_DIR/scripts/tracker.py' ]]"
check "debrief.py exists" "[[ -f '$PROJECT_DIR/scripts/debrief.py' ]]"
check "base-estimates.yml exists" "[[ -f '$DC/planning/base-estimates.yml' ]]"
check "estimates.csv exists" "[[ -f '$DC/kpis/estimates.csv' ]]"
check "calibration.json exists" "[[ -f '$DC/kpis/calibration.json' ]]"
check "model-policy.json exists" "[[ -f '$DC/kpis/model-policy.json' ]]"
check "planning-gate.md rule exists" "[[ -f '$DC/rules/planning-gate.md' ]]"
check "/debrief skill exists" "[[ -f '$PROJECT_DIR/.claude/skills/debrief/SKILL.md' ]]"
check "cost-ledger has duration_sec" "head -1 '$DC/cost-ledger.csv' | grep -q duration_sec"
check "TRACKER_BACKEND set" "grep -q '^TRACKER_BACKEND=' '$DC/project.conf'"
check_warn "cc10x patterns.md exists" "[[ -f '$PROJECT_DIR/.claude/cc10x/patterns.md' ]]"
report_stage 8 "Learning Loop"

# --- Stage 9: Communication ---
stage 9 "Communication"
check_warn "inbox/critical/ exists" "[[ -d '$DC/inbox/critical' ]]"
check_warn "inbox/approval/ exists" "[[ -d '$DC/inbox/approval' ]]"
check_warn "inbox/digest/ exists" "[[ -d '$DC/inbox/digest' ]]"
check_warn "inbox/archive/ exists" "[[ -d '$DC/inbox/archive' ]]"
check_warn "message templates exist" "[[ -f '$DC/comms/templates/critical-template.md' ]]"
check_warn "comms config exists" "[[ -f '$DC/comms/config.yml' ]]"
report_stage 9 "Communication (Inbox Protocol)"

# --- Stage 10: KPI Infrastructure ---
stage 10 "KPI Infrastructure"
check_warn "bug-ledger.csv exists" "[[ -f '$DC/kpis/bug-ledger.csv' ]]"
check_warn "sprint-log.csv exists" "[[ -f '$DC/kpis/sprint-log.csv' ]]"
check_warn "review-log.csv exists" "[[ -f '$DC/kpis/review-log.csv' ]]"
check_warn "release-log.csv exists" "[[ -f '$DC/kpis/release-log.csv' ]]"
check_warn "security-audit-log.csv exists" "[[ -f '$DC/kpis/security-audit-log.csv' ]]"
check_warn "e2e-test-log.csv exists" "[[ -f '$DC/kpis/e2e-test-log.csv' ]]"
check_warn "retrospective template exists" "[[ -f '$DC/kpis/templates/retrospective-template.md' ]]"
check_warn "sprint retro template exists" "[[ -f '$DC/kpis/templates/sprint-retrospective-template.md' ]]"
check_warn "kpi-summary.sh is executable" "[[ -x '$PROJECT_DIR/scripts/kpi-summary.sh' ]]"
report_stage 10 "KPI Infrastructure"

echo ""
echo "=================================="
SUMMARY_FAIL=0; SUMMARY_WARN=0
[[ $WARN -gt 0 ]] && SUMMARY_WARN=1
[[ $FAIL -gt 0 ]] && SUMMARY_FAIL=1
echo " Summary: $PASS/$TOTAL checks passed, $WARN warnings, $FAIL failures"
if [[ $SUMMARY_FAIL -eq 1 ]]; then
  echo " Result: FAIL -- address failures before pipeline is operational"
elif [[ $SUMMARY_WARN -eq 1 ]]; then
  echo " Result: PASS with warnings"
else
  echo " Result: ALL CLEAR"
fi
echo "=================================="
