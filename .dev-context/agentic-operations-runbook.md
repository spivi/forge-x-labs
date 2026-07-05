# Agentic Operations Runbook

> How to operate the 8-agent AI development pipeline for your project.
> This guide assumes you're familiar with Claude Code and GitHub.

---

## 1. Agent Overview

Eight specialized AI agents handle the software development lifecycle. You interact directly with **2** of them; the other 6 work autonomously.

### Human-Facing Agents

| Agent | Spec | How You Interact | What It Does |
|-------|------|-----------------|--------------|
| **Product Manager** | `agents/product_manager.md` | `/prd`, inbox approvals | Writes PRDs, creates tickets, proposes roadmap |
| **Budget Review** | `agents/budget_review.md` | `/cost`, Scrum Master pre-check | Reads cost ledger, compares against budgets |

### Internal Agents (No Direct Interaction)

| Agent | Spec | Trigger | What It Does |
|-------|------|---------|--------------|
| **Scrum Master** | `agents/scrum_master.md` | `/sprint` skill | Plans sprints, assigns tickets, tracks velocity |
| **Developer Worker** | `agents/developer.md` | Spawned by Scrum Master | Implements features on worktree branches |
| **Code Reviewer** | `agents/code_reviewer.md` | GitHub Action on PR | Automated code review against project rules |
| **Security Architect** | `agents/security_architect.md` | GitHub Action on PR | Security-focused review, dependency audits |
| **E2E Tester** | `agents/e2e_tester.md` | GitHub Action on PR | Runs end-to-end test suite, reports results |
| **Handoff Manager** | `agents/handoff_manager.md` | `/release` skill | Generates release notes, manages git tags |

### Pipeline Flow

```
You (ideas) -> PM -> Scrum Master -> Developer -> Code Reviewer + Security + E2E -> Handoff Manager
                                                                                      |
Budget Review checks costs on demand <-<-<-<-<-<-<-<-<-<- Release -> You (approval)
```

---

## 2. Daily Operations

### Starting a Session

When you open Claude Code, the session-start hook runs automatically:

1. Loads `STATUS.md`, `DECISIONS.md`, and project context
2. Scans inbox for PENDING items
3. Displays summary:
   - Critical items (red) -- act before working
   - Approval items (yellow) -- decide when ready
   - Unread digests (blue) -- read at convenience

**If you see critical items**: Read the file in `.dev-context/inbox/critical/`, write your decision in the "Your Response" section, and change `Status: PENDING` to your decision.

### Checking Inbox Manually

```bash
ls .dev-context/inbox/critical/
ls .dev-context/inbox/approval/
ls .dev-context/inbox/digest/
```

Or read any specific message:
```bash
cat .dev-context/inbox/approval/<filename>.md
```

### Responding to Inbox Messages

1. Open the message file
2. Change `**Status**: PENDING` to `APPROVED`, `REJECTED`, or `ACKNOWLEDGED`
3. Optionally write feedback in the "Your Response" section
4. Save the file -- the agent reads it on next activation
5. Move processed files to `.dev-context/inbox/archive/` when done

### Running a Sprint

```
/sprint plan    # Scrum Master selects tickets, assigns developers
/sprint status  # View active work, blockers, progress
```

The Scrum Master reads the backlog, checks budget with Budget Review, and spawns Developer Workers on separate git worktrees.

### Checking Costs

```
/cost                              # Interactive cost report (Budget Review)
bash scripts/budget-analysis.sh    # Detailed analysis with anomaly detection
bash scripts/kpi-summary.sh        # Cross-agent KPI dashboard
```

---

## 3. Periodic Operations

### Sprint Retrospective (End of Sprint)

1. Run the KPI summary:
   ```bash
   bash scripts/kpi-summary.sh
   ```
2. Review per-agent metrics (cost, bugs, review cycles, test pass rate)
3. Use the sprint retrospective template:
   ```
   .dev-context/kpis/templates/sprint-retrospective-template.md
   ```
4. Log sprint results to `.dev-context/kpis/sprint-log.csv`

### Budget Review (Weekly)

1. Run the budget analysis:
   ```bash
   bash scripts/budget-analysis.sh
   ```
2. Check for cost anomalies (script flags sessions with >5x divergence)
3. If tuning is needed, update `.dev-context/budgets.yml`
4. Budget limits in `budgets.yml`:
   - `daily.total` -- max spend per day across all providers
   - `weekly.total` -- max spend per week
   - `per_session.max_cost` -- max cost for a single agent session
   - `per_ticket.max_cost` -- max cost for all sessions on one ticket

### Pipeline Health Check (Monthly or After Major Changes)

```bash
bash scripts/validate-pipeline.sh
```

Validates all 10 pipeline stages have prerequisites met:
- Agent specs exist and are non-empty
- GitHub workflows are present
- KPI CSV files have correct headers
- Inbox directories and templates exist
- Scripts are executable

Results are logged to `.dev-context/kpis/pipeline-validation-log.csv`.

### Dependency Audit (Triggered by Security Architect)

The `dependency-audit.yml` GitHub Action runs automatically. If the Security Architect finds critical CVEs, it writes to `inbox/critical/`. Otherwise, results stay in GitHub.

---

## 4. Troubleshooting

### Budget Exceeded

**Symptom**: Budget Review sets `BUDGET_EXCEEDED` in STATUS.md. Scrum Master stops spawning new sessions.

**Resolution**:
1. Read the critical inbox message for details
2. Options:
   - Increase budget in `budgets.yml` (edit the relevant limit)
   - Wait for the budget period to reset (daily resets at midnight UTC)
   - Reduce scope of remaining tickets
3. Write your decision in the inbox file
4. Remove `BUDGET_EXCEEDED` from STATUS.md if budget was increased

### Security Critical Finding

**Symptom**: Security Architect writes to `inbox/critical/` and blocks the PR.

**Resolution**:
1. Read the critical inbox message
2. Check the linked PR for details
3. Either:
   - Have the developer fix the vulnerability (highest priority)
   - Accept the risk with justification (document in DECISIONS.md)
4. Respond in the inbox file

### Stuck Developer / Blocked Ticket

**Symptom**: A ticket stays `in_progress` for too long, or STATUS.md shows a blocker.

**Resolution**:
1. Check STATUS.md Active Worktrees table for the ticket status
2. If the developer hit a technical blocker:
   - Open a Claude Code session in the relevant worktree
   - Investigate and unblock manually
3. If the blocker is a dependency on another ticket:
   - Re-prioritize with Scrum Master (`/sprint`)
4. If the blocker is a human decision needed:
   - Check inbox for approval requests

### Pipeline Validation Failures

**Symptom**: `validate-pipeline.sh` reports FAIL for a stage.

**Resolution by stage**:

| Stage | Common Fix |
|-------|-----------|
| Idea Intake | Create missing PM spec or `/prd` skill |
| Backlog Management | Ensure `budgets.yml` exists |
| Development | Set up `.venv/`, install pre-commit hooks |
| Code Review | Check `.github/workflows/ai-code-review.yml` |
| E2E Testing | Verify test directory and workflow exist |
| Release Management | Ensure `release.yml` workflow and git tags work |
| Cost Governance | Check `cost-ledger.csv` has data rows |
| Context Sync | Verify session-start hook in `.claude/hooks/` |
| Communication | Create missing inbox dirs or templates |
| KPI Infrastructure | Run scripts to initialize CSV files |

### Pre-commit Hook Failures

**Symptom**: Commit blocked by ruff, mypy, or pytest.

**Resolution**:
```bash
# Check what failed
pre-commit run --all-files

# Fix formatting
ruff format .

# Fix lint issues
ruff check --fix .

# Type errors (manual fix required)
mypy app/ --strict

# Test failures
PYTHONPATH=. .venv/bin/pytest
```

### Cost Data Anomalies

**Symptom**: `budget-analysis.sh` reports sessions with >5x cost divergence.

**Resolution**:
1. Check `scripts/log-session-cost.sh` (the hook that writes to cost-ledger)
2. Common causes:
   - Cumulative session cost logged instead of per-turn cost
   - Cache token pricing applied incorrectly
   - Wrong token field read from transcript
3. Fix the hook, then re-run analysis

---

## 5. Key Files Reference

### Agent Definitions

| File | Agent |
|------|-------|
| `.dev-context/agents/product_manager.md` | Product Manager |
| `.dev-context/agents/scrum_master.md` | Scrum Master |
| `.dev-context/agents/developer.md` | Developer Worker |
| `.dev-context/agents/code_reviewer.md` | Code Reviewer |
| `.dev-context/agents/security_architect.md` | Security Architect |
| `.dev-context/agents/e2e_tester.md` | E2E Tester |
| `.dev-context/agents/handoff_manager.md` | Handoff Manager |
| `.dev-context/agents/budget_review.md` | Budget Review |

### Configuration

| File | Purpose | Owner |
|------|---------|-------|
| `.dev-context/budgets.yml` | Cost limits and pricing | Human |
| `.dev-context/comms/config.yml` | Communication protocol config | Human |
| `.dev-context/comms/communication-protocol.md` | Full protocol spec | Human |
| `STATUS.md` | Current project state | All agents |
| `DECISIONS.md` | Architecture decisions | PM + Human |

### KPI Tracking

| File | Owner | Purpose |
|------|-------|---------|
| `.dev-context/cost-ledger.csv` | SessionEnd hook | Per-session cost tracking |
| `.dev-context/kpis/sprint-log.csv` | Scrum Master | Sprint velocity |
| `.dev-context/kpis/review-log.csv` | Code Reviewer | Review quality |
| `.dev-context/kpis/bug-ledger.csv` | Developer | Bug traceability |
| `.dev-context/kpis/e2e-test-log.csv` | E2E Tester | Test pass rates |
| `.dev-context/kpis/security-audit-log.csv` | Security Architect | Audit results |
| `.dev-context/kpis/release-log.csv` | Handoff Manager | Release quality |
| `.dev-context/kpis/pipeline-validation-log.csv` | Operator | Pipeline health |

### Communication

| Path | Purpose |
|------|---------|
| `.dev-context/inbox/critical/` | Urgent items (budget, security) |
| `.dev-context/inbox/approval/` | Items needing your decision |
| `.dev-context/inbox/digest/` | Informational reports |
| `.dev-context/inbox/archive/` | Processed items |
| `.dev-context/comms/templates/` | Message templates for agents |

### Scripts

| Script | Purpose | When to Run |
|--------|---------|-------------|
| `scripts/validate-pipeline.sh` | Check all 10 pipeline stages | Monthly, after changes |
| `scripts/budget-analysis.sh` | Analyze costs vs budgets | Weekly, on demand |
| `scripts/kpi-summary.sh` | Cross-agent KPI dashboard | Sprint retrospective |

### GitHub Workflows

| Workflow | Trigger | Agent |
|----------|---------|-------|
| `ci.yml` | Push/PR | -- (standard CI) |
| `ai-code-review.yml` | PR opened/updated | Code Reviewer |
| `ai-security-review.yml` | PR opened/updated | Security Architect |
| `e2e-tests.yml` | PR opened/updated | E2E Tester |
| `dependency-audit.yml` | Schedule/manual | Security Architect |
| `release.yml` | Tag push / manual | Handoff Manager |

---

## 6. Command Quick Reference

| Command | What It Does |
|---------|-------------|
| `/sprint plan` | Plan a sprint (Scrum Master) |
| `/sprint status` | View sprint status |
| `/cost` | Cost report (Budget Review) |
| `/prd <idea>` | Generate PRD (Product Manager) |
| `/review <PR>` | Review a PR (Code Reviewer) |
| `/security-review <PR>` | Security review (Security Architect) |
| `/release` | Generate release notes (Handoff Manager) |
| `/develop` | Tiered development pipeline |
| `/hotfix` | Emergency production fix |
| `/monitor` | Production health check |
| `/diagnose` | Root cause investigation |
| `bash scripts/validate-pipeline.sh` | Pipeline health check |
| `bash scripts/budget-analysis.sh` | Budget analysis |
| `bash scripts/kpi-summary.sh` | KPI summary |
