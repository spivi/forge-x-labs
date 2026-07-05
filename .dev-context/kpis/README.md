# KPI Tracking Infrastructure

> Schema registry for all KPI data sources. Each CSV is owned by a
> specific agent, has a defined schema, and feeds into the sprint
> retrospective.
>
> Full KPI framework: `agent-kpis.md`

## CSV Ledgers

| File | Owner | Readers | Purpose |
|------|-------|---------|---------|
| `bug-ledger.csv` | Developer Worker | Scrum Master, Budget Review | Bug-to-feature traceability |
| `sprint-log.csv` | Scrum Master | Budget Review, PM | Sprint completion metrics |
| `review-log.csv` | Code Reviewer | Scrum Master | PR review accuracy |
| `release-log.csv` | Handoff Manager | Scrum Master, PM | Release cadence tracking |
| `security-audit-log.csv` | Security Architect | Scrum Master | Vulnerability detection metrics |
| `e2e-test-log.csv` | E2E Tester | Scrum Master | Test reliability metrics |
| `../cost-ledger.csv` | SessionEnd hook | Budget Review, SM, PM | Session-level cost tracking |
| `pipeline-validation-log.csv` | Human / validate script | All | Pipeline health checks |

## Schemas

### bug-ledger.csv
```
bug_id,title,severity,feature_ticket,feature_pr,developer_session,root_cause,category,retrospective_done
```
Categories: `missing_validation`, `missing_edge_case`, `wrong_logic`, `missing_test`, `integration_gap`, `prompt_drift`, `stale_context`

### sprint-log.csv
```
sprint_id,start_date,end_date,planned_tickets,completed_tickets,conflicts,avg_cycle_hours,blockers_raised,blockers_resolved
```

### review-log.csv
```
pr_number,branch,review_cycles,violations_found,false_positives,turnaround_minutes,verdict,bugs_escaped
```

### release-log.csv
```
version,date,features_count,bugfixes_count,notes_approved_first_draft,notification_sent,human_edits
```

### security-audit-log.csv
```
timestamp,pr_number,branch,risk_level,findings_count,critical_count,dependency_cves,false_positives,verdict,response_time_minutes
```

### e2e-test-log.csv
```
timestamp,pr_number,branch,tests_total,tests_passed,tests_failed,coverage_percent,coverage_delta,execution_time_seconds,flaky_tests,verdict,report_url
```

### cost-ledger.csv (at ../)
```
timestamp,agent,session_id,provider,model,input_tokens,output_tokens,cache_creation_tokens,cache_read_tokens,compute_cost_usd,billing_type,billed_usd,ticket,session_start,session_end,duration_sec
```
- `compute_cost_usd`: Estimated cost from token counts (includes cache)
- `billing_type`: `subscription` (billed_usd=0) or `api` (billed_usd=compute_cost)
- `billed_usd`: Actual wallet impact -- the number that matters for budgets
- `session_start` / `session_end`: First/last transcript timestamps (ISO-8601; empty if absent)
- `duration_sec`: Active session wall-clock in seconds -- the **actual** that `/debrief` calibrates `estimate_minutes` against (0 if timestamps absent)

### pipeline-validation-log.csv
```
timestamp,stages_pass,stages_warn,stages_fail,total_checks,checks_pass,notes
```

## Templates

| Template | Purpose | Location |
|----------|---------|----------|
| Bug retrospective | Per-bug analysis and improvement plan | `templates/retrospective-template.md` |
| Sprint retrospective | Unified 8-agent scorecard for sprint review | `templates/sprint-retrospective-template.md` |

## Aggregation

Run `scripts/kpi-summary.sh` to generate a formatted summary of all
KPI data for use in sprint retrospectives.
