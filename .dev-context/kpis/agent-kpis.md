# Agent KPI Framework

> Every agent has measurable KPIs that drive continuous improvement.
> KPIs are tracked per sprint, reviewed in retrospectives, and used to
> tune agent prompts, rules, and policies.

## File Locations

| File | Path | Status |
|------|------|--------|
| Cost ledger | `.dev-context/cost-ledger.csv` | Ready |
| Bug ledger | `.dev-context/kpis/bug-ledger.csv` | Ready |
| Sprint log | `.dev-context/kpis/sprint-log.csv` | Ready |
| Review log | `.dev-context/kpis/review-log.csv` | Ready |
| Release log | `.dev-context/kpis/release-log.csv` | Ready |
| Security audit log | `.dev-context/kpis/security-audit-log.csv` | Ready |
| E2E test log | `.dev-context/kpis/e2e-test-log.csv` | Ready |
| Pipeline validation log | `.dev-context/kpis/pipeline-validation-log.csv` | Ready |
| Bug retrospective template | `.dev-context/kpis/templates/retrospective-template.md` | Ready |
| Sprint retro template | `.dev-context/kpis/templates/sprint-retrospective-template.md` | Ready |
| KPI summary script | `scripts/kpi-summary.sh` | Ready |
| Schema registry | `.dev-context/kpis/README.md` | Ready |

## KPI Data Sources

| Source | Location | Updated By |
|--------|----------|-----------|
| Bug ledger | `.dev-context/kpis/bug-ledger.csv` | Developer Worker, Scrum Master |
| Cost ledger | `.dev-context/cost-ledger.csv` | SessionEnd hook |
| Sprint log | `.dev-context/kpis/sprint-log.csv` | Scrum Master |
| Review log | `.dev-context/kpis/review-log.csv` | Code Reviewer |
| Release log | `.dev-context/kpis/release-log.csv` | Handoff Manager |

---

## Scrum Master -- Flow & Coordination

**North Star**: Continuous, conflict-free feature delivery.

| KPI | Metric | Target | How to Measure |
|-----|--------|--------|----------------|
| **Feature throughput** | Tickets completed per sprint | >= 3 / sprint | Count tickets moved to Done in sprint period |
| **Conflict rate** | File conflicts between active branches | 0 per sprint | Count conflicts detected during sprint (from STATUS.md) |
| **Sprint completion rate** | % of planned tickets that merged in the sprint | >= 80% | Planned vs. actually merged |
| **Assignment accuracy** | % of tickets that completed without scope change | >= 90% | Tickets where acceptance criteria did not change post-assignment |
| **Cycle time** | Avg hours from assignment to PR merged | Decreasing trend | Timestamps: worktree created -> PR merged |
| **Blocker resolution time** | Avg hours from blocker raised to resolved | < 4h | Timestamps from STATUS.md blocker entries |

### Tracking

```csv
# .dev-context/kpis/sprint-log.csv
sprint_id,start_date,end_date,planned_tickets,completed_tickets,conflicts,avg_cycle_hours,blockers_raised,blockers_resolved
```

---

## Developer Worker -- Quality & Reliability

**North Star**: Zero bugs traced back to agent-written code.

| KPI | Metric | Target | How to Measure |
|-----|--------|--------|----------------|
| **Bug rate** | Bugs filed per feature delivered | 0 bugs / feature | Count bugs linked to features (bug ledger) |
| **First-time approval rate** | % of PRs approved by Code Reviewer on first review | >= 80% | PRs approved without request-changes |
| **Test coverage per ticket** | Line coverage of changed files | >= 85% | Coverage report from PR |
| **Rework rate** | % of tickets requiring post-merge fixes | < 10% | Bug-fix PRs linked to original feature PR |
| **Rule violation rate** | Violations per review | Decreasing trend | Count from Code Reviewer reports |

### Bug -> Feature Traceability

Every bug filed in the system **must** be linked to the originating feature:

```csv
# .dev-context/kpis/bug-ledger.csv
bug_id,title,severity,feature_ticket,feature_pr,developer_session,root_cause,category,retrospective_done
```

**Bug categories** (for pattern detection):
- `missing_validation` -- Input not validated
- `missing_edge_case` -- Happy path only, edge case missed
- `wrong_logic` -- Logic error in implementation
- `missing_test` -- No test covered the failure path
- `integration_gap` -- Works in isolation, fails when integrated
- `prompt_drift` -- Agent misinterpreted acceptance criteria
- `stale_context` -- Agent worked on outdated code/state

### Retrospective Process

When a bug is filed and traced to a feature:

1. **Document** the bug in `bug-ledger.csv` with root cause and category
2. **Analyze** what the Developer Worker missed and why
3. **Improve** the agent: Propose a concrete change (rule, prompt, process) to prevent recurrence
4. **Track** whether the improvement worked by monitoring the bug category trend

---

## Budget Review Agent -- Financial Discipline

**North Star**: Always on budget, with proactive economic intelligence.

| KPI | Metric | Target | How to Measure |
|-----|--------|--------|----------------|
| **Budget adherence** | Actual spend / budgeted spend per period | 80-100% | cost-ledger.csv vs. budgets.yml |
| **Overrun incidents** | Times a period budget was exceeded | 0 per month | Circuit breaker trigger count |
| **Forecast accuracy** | Predicted vs. actual weekly cost | Within 15% | Compare weekly forecast to actual |
| **Cost per feature** | Average cost to implement one ticket | Decreasing trend | cost-ledger.csv aggregated by ticket |
| **Flag response time** | Time from anomaly detected to human notified | < 1 hour | Timestamps in cost reports |
| **Economic propositions** | Proactive cost-saving suggestions per sprint | >= 1 per sprint | Count suggestions in cost reports |

---

## Product Manager -- Innovation & Alignment

**North Star**: Ship the right things, discover new opportunities, stay ahead of market.

| KPI | Metric | Target | How to Measure |
|-----|--------|--------|----------------|
| **Innovation rate** | New feature ideas generated per week | >= 2 per week | Count new PRDs created |
| **Roadmap alignment** | % of shipped features that were on the roadmap | >= 70% | Compare shipped features to roadmap |
| **PRD approval rate** | % of PRDs approved by human on first review | >= 80% | PRDs approved vs. total submitted |
| **Criteria clarity score** | % of tickets completed without criteria change | >= 90% | Tickets where AC didn't change post-creation |
| **Go-to-market ideas** | GTM suggestions per release | >= 1 per release | Count GTM items in release planning |

---

## Code Reviewer -- Review Accuracy

**North Star**: Catch real issues, no false positives, fast turnaround.

| KPI | Metric | Target | How to Measure |
|-----|--------|--------|----------------|
| **Bug escape rate** | Bugs in prod that were in reviewed PRs | 0 per sprint | Bugs linked to PRs that passed review |
| **False positive rate** | Review violations that were incorrect | < 5% | Developer disputes upheld by human |
| **Review turnaround** | Time from PR opened to review posted | < 10 min | Timestamps: PR created -> review comment |
| **Rule coverage** | % of rules that have at least 1 check in reviews | 100% | Cross-reference rules/ vs. review checklist |
| **Re-review rate** | % of PRs needing >2 review cycles | < 20% | Count review cycles per PR |

### Tracking

```csv
# .dev-context/kpis/review-log.csv
pr_number,branch,review_cycles,violations_found,false_positives,turnaround_minutes,verdict,bugs_escaped
```

---

## Security Architect -- Vulnerability Prevention

**North Star**: Zero vulnerabilities escape to production; every feature has a threat model.

| KPI | Metric | Target | How to Measure |
|-----|--------|--------|----------------|
| **Vulnerability escape rate** | Security bugs in prod that were in reviewed PRs | 0 per sprint | Security bugs linked to PRs that passed review |
| **Dependency CVE coverage** | % of dependencies scanned against CVE databases | 100% | pip-audit coverage reports |
| **Review turnaround** | Time from PR opened to security review posted | < 15 min | Timestamps: PR created -> security review comment |
| **False positive rate** | Security findings that were incorrect | < 10% | Developer disputes upheld by human |
| **Threat model coverage** | % of new features with threat model before implementation | 100% | PRDs with threat model advisory attached |

### Tracking

```csv
# .dev-context/kpis/security-audit-log.csv
timestamp,pr_number,branch,risk_level,findings_count,critical_count,dependency_cves,false_positives,verdict,response_time_minutes
```

---

## E2E Tester -- Coverage & Reliability

**North Star**: No regressions reach production.

| KPI | Metric | Target | How to Measure |
|-----|--------|--------|----------------|
| **Regression catch rate** | % of regressions caught before merge | 100% | Regressions caught vs. total |
| **Test reliability** | % of test runs with no flaky failures | >= 95% | Flaky test incidents / total runs |
| **Coverage delta** | Coverage change per PR | Non-negative | Coverage reports before/after |
| **Test execution time** | Full suite runtime | < 5 min | CI timing data |
| **Critical path coverage** | % of critical user flows covered | 100% | Audit against flow list |

---

## Handoff Manager -- Release Quality

**North Star**: Every release is well-documented and stakeholders are informed.

| KPI | Metric | Target | How to Measure |
|-----|--------|--------|----------------|
| **Release cadence** | Releases per sprint | >= 1 per sprint | Count GitHub Releases |
| **Notes accuracy** | % of releases where notes match actual changes | 100% | Human review of release notes |
| **Notification delivery** | % of releases with stakeholder notification sent | 100% | Notification logs |
| **First-draft approval rate** | % of release notes approved without edits | >= 80% | Notes approved vs. edited |

### Tracking

```csv
# .dev-context/kpis/release-log.csv
version,date,features_count,bugfixes_count,notes_approved_first_draft,notification_sent,human_edits
```

---

---

## Cross-Agent KPI: Sprint Retrospective

After each sprint, all agent KPIs feed into a unified retrospective:

```markdown
## Sprint N Retrospective

### Scorecard
| Agent | Key Metric | Score | Trend |
|-------|-----------|-------|-------|
| Scrum Master | Throughput | N/N planned | |
| Developer | Bug rate | N bugs / N features | |
| Budget Review | Budget adherence | N% | |
| PM | Innovation rate | N ideas | |
| Code Reviewer | Bug escape rate | N | |
| Security Architect | Vuln escape rate | N | |
| E2E Tester | Regression catch | N% | |
| Handoff Manager | Release cadence | N release | |
```

---

## Activation Checklist

Each agent's KPI tracking requires resources and permissions. During agent
implementation, validate the following:

| Agent | Resource Validation |
|-------|--------------------|
| **Scrum Master** | Can read/write STATUS.md, can run `gh issue list`, can create worktrees, sprint-log.csv writable |
| **Developer Worker** | Can run tests, linters, type checker; can push branches; can run `gh pr create`; bug-ledger.csv writable |
| **Budget Review** | budgets.yml readable; cost-ledger.csv readable; can write STATUS.md blockers |
| **Code Reviewer** | ANTHROPIC_API_KEY secret set; can post PR comments; can approve/reject PRs; review-log.csv writable |
| **Security Architect** | ANTHROPIC_API_KEY secret set; `pip-audit`, `bandit`, `detect-secrets` installed in CI; can post PR comments; security-audit-log.csv writable |
| **E2E Tester** | Can run full test suite; can post PR comments; can add labels to PRs |
| **Handoff Manager** | Can read git log; can create GitHub Releases; release-log.csv writable |
| **PM Agent** | Can read codebase; can create GitHub Issues (syncs to Linear); can write to prds/ |
