# AI Agent Pipeline

> Autonomous development pipeline where specialized AI agents handle
> product management, development, code review, testing, and release handoff.

## Architecture

```
                        +------------------------------------------------+
                        |        Budget Review (Cost Governance)          |
                        |  reads cost ledger, compares against budgets   |
                        +------------------+-----------------------------+
                                           | budget check
                                           v
Human (You)                         Scrum Master --Assigns--> Developer Workers
  |  Ideas, PRD approval,               ^ |                      | (parallel)
  |  release approval,                  | | monitors              |
  |  budget limits                      | |<---- status ----------|
  |                                     | |                       v
  v                                     | |                  Code Reviewer
Product Manager --PRDs + Tickets--------+ |                    |  ^
                                          |                    v  | fix loop
                                          |                  Code Fixer
                                          |                       |
                                          |                       v
                                          |                  E2E Tester
                                          |                       |
                                          |                       v merge
                                          |              Handoff Manager
                                          |                       |
                                          |                       v
                                          |              Notification -> Human
                                          |
                                          +-- Escalations -> Human
```

## Agent Roles

| Layer | Agent | Trigger | Status |
|-------|-------|---------|--------|
| 1 | **Scrum Master** | Manual (`/sprint`), scheduled, or on new tickets | Planned |
| 2 | **Developer Worker** | Spawned by Scrum Master (one per ticket) | Planned |
| 3 | **Code Reviewer** | PR opened/updated (GitHub Action) | Planned |
| 3b | **Code Fixer** | Auto-fix triggered by Code Reviewer FAIL (up to 3 iterations) | Planned |
| 4 | **E2E Tester** | Code review approved | Planned |
| 5 | **Product Manager** | Scheduled, or human provides ideas | Planned |
| 6 | **Handoff Manager** | Merge to `main`, manual `/release` | Planned |
| 7 | **Budget Review** | Manual (`/cost`) or Scrum Master pre-check | Planned |

## Agent Contract Format

Every agent definition file follows this structure:

```markdown
## Identity
- Role, responsibilities, boundaries

## Trigger
- What causes this agent to activate

## Input
- What context/data it receives

## Tools
- What tools/capabilities it has access to

## Process
- Step-by-step workflow

## Output
- What it produces, where it writes

## Human Gates
- When it must stop and ask the human

## Failure Modes
- What to do when things go wrong
```

## Shared State

All agents coordinate through these files:

| File | Purpose | Owner |
|------|---------|-------|
| `STATUS.md` | Current state, active worktrees, blockers | All agents (read/write) |
| `DECISIONS.md` | Architecture constraints | PM + Human (write), all (read) |
| `.dev-context/agents/*.md` | Agent definitions | Human (write), agents (read) |
| Active Worktrees table | Parallel work coordination | Scrum Master + Developers |
| `.dev-context/budgets.yml` | Spend limits and alert thresholds | Human (write), Budget Review (read) |
| `.dev-context/cost-ledger.csv` | Running cost log per session/ticket | SessionEnd hook (write), all (read) |

## Invocation Methods

| Method | Use Case |
|--------|----------|
| **Skill** (`/sprint`) | Manual sprint planning from Claude Code session |
| **GitHub Action** | Automated code review on PR events |
| **Claude Code CLI** | `claude -p "prompt" --allowedTools ...` for scripted invocation |
| **Claude Agent SDK** | Custom orchestrator service (future) |
| **Scheduled Action** | Cron-triggered planning or health checks |

## Adding a New Agent

1. Create `agent_name.md` in this directory following the contract format
2. If the agent needs a manual trigger, create a skill in `.claude/skills/`
3. If the agent needs automated triggering, add a GitHub Action in `.github/workflows/`
4. Update the Agent Roles table above
5. Add a decision entry in `DECISIONS.md` if the agent introduces architectural changes
