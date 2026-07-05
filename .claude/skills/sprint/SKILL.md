---
name: sprint
description: "Scrum master: plan sprints, spawn parallel developer agents, manage merge ordering, track budget. Use when: /sprint, plan sprint, assign work, standup, sprint status, merge queue, sprint planning. Actions: plan (default), execute [ticket-ids], status, merge, watch [ticket-ids], assign <ticket>, unblock <ticket>."
---

# Sprint Skill (Scrum Master)

Orchestrate parallel development work. Read the full agent definition
at `.dev-context/agents/scrum_master.md` before proceeding.

## Instructions

### Action: `plan` (default)

Plan the next sprint of work.

1. **Read context** (mandatory, in order):
   - `.dev-context/project.conf` → project ID
   - `STATUS.md` → active worktrees, blockers, current phase
   - `DECISIONS.md` → architectural constraints
   - **Ticket backlog**: Linear MCP `list_issues` (team filter: {{TICKET_PREFIX}}) (primary) → `gh issue list` (fallback)
   - **Never select** an issue labeled `handoff:human-review` — it is a human-only review
     handoff (`.dev-context/rules/iteration-gate.md`); exclude it from candidates entirely
     (`gh issue list ... --search '-label:"handoff:human-review"'`).

1b. **Check budget status** (mandatory):
   - Read `.dev-context/budgets.yml` for budget limits and alert thresholds
   - Read `.dev-context/cost-ledger.csv` and sum `billed_usd` for current period (daily)
   - Calculate: `spend_pct = (period_spend / period_budget) * 100`
   - **If `BUDGET_EXCEEDED` blocker in STATUS.md**: STOP. Print budget status. Refuse to spawn agents. Explain why.
   - **If spend >= 90%**: Include CRITICAL warning in output. Suggest using cheaper models (claude-haiku-4-5) for P2/P3 tickets.
   - **If spend >= 70%**: Include cost WARNING in output. Proceed with caution.
   - **Otherwise**: Include budget status line in output (spend/budget, percentage).
   - **Subscription quota gate** (when `budgets.yml::subscription.provider` is set):
     also run `python scripts/subscription_quota.py status`. The most-restrictive of
     (dollar band, quota band) wins — HARD-STOP at CRITICAL/EXCEEDED, WARN proceeds with
     caution. Fail-open: disabled (provider null) or unreadable → dollar gate only.

1c. **Status-drift check** (fail-soft): `python scripts/status_drift.py check` detects
   orphaned worktree rows / stale Queued tickets in STATUS.md. Surface the JSON report.
   Honor `STATUS_DRIFT_MODE` in `project.conf`: `warn` (default) → note it and proceed;
   `block` → reconcile (`status_drift.py sanitize`) before spawning; `off` → skip. Never
   crashes the plan (drift detection is advisory).

2. **Assess capacity**:
   - Count active worktrees in STATUS.md
   - Max parallel agents: 3
   - Available slots = 3 - active count

3. **Select tickets** (for each available slot):
   - Query open tickets via Linear MCP `list_issues` (team: {{TICKET_PREFIX}}). Fallback: `gh issue list`
   - Pick highest-priority "ready" ticket
   - Verify no file conflicts with active branches
   - Verify no unmet dependencies
   - Skip tickets without clear acceptance criteria (flag to human)
4. **Present sprint plan** to the human:
   ```
   ## Sprint Plan

   **Capacity**: <active>/<max> slots in use, <available> available
   **Budget**: $<spend> / $<budget> daily (<pct>%) [OK | WARNING | CRITICAL | EXCEEDED]

   ### Proposed Assignments

   | Ticket | Title | Priority | Est. Files | Conflicts |
   |--------|-------|----------|------------|-----------|
   | {{TICKET_PREFIX}}-NNN | ... | P1 | app/x.py, tests/... | None |

   ### Blocked/Skipped
   - {{TICKET_PREFIX}}-NNN: <reason>

   ### Active Work
   | Ticket | Branch | Status | Last Commit |
   |--------|--------|--------|-------------|
   | {{TICKET_PREFIX}}-NNN | feat/... | in-progress | 2h ago |
   ```

5. **On human approval**: Either run `/sprint execute` to auto-spawn agents,
   or manually assign with `/sprint assign` per scrum_master.md Process §3

### Action: `execute [ticket-ids...]`

Execute the sprint plan by spawning parallel Task agents that implement
tickets autonomously. Handles all human gates in the main session first,
then spawns background agents for Phases 4-7.

**Usage**: `/sprint execute {{TICKET_PREFIX}}-NNN {{TICKET_PREFIX}}-NNN` or `/sprint execute` (uses
tickets from last `plan` output).

#### Phase A: Pre-flight Checks

1. **Read context** (same as `plan` action):
   - `.dev-context/project.conf`, `STATUS.md`, `DECISIONS.md`
   - `.dev-context/budgets.yml` + `.dev-context/cost-ledger.csv`

2. **Budget gate**:
   - Calculate remaining: `remaining = daily_budget - today_spend`
   - Estimate cost per agent: ~$8-12 (from `per_ticket.alert_at`)
   - Verify: `remaining >= (num_tickets * estimated_cost)`
   - If insufficient: warn human, suggest reducing count or cheaper models
   - If `BUDGET_EXCEEDED`: STOP immediately

3. **Capacity check**:
   - Available slots = 3 - active worktree count
   - Verify requested tickets <= available slots

4. **Validate each ticket**:
   - Ticket exists (Linear MCP `get_issue` or `gh issue view`)
   - PRD exists at `.dev-context/prds/{{TICKET_PREFIX}}-<NNN>.md`
   - Status is "ready" / "Backlog" / "Todo" (not "Done" / "In Progress")
   - No file conflicts with active worktrees (cross-ref PRD scope tables)
   - If validation fails: exclude ticket, continue with remaining

#### Phase B: Batch Human Gates (Sequential)

For each validated ticket, in priority order:

1. **Read the PRD** at `.dev-context/prds/{{TICKET_PREFIX}}-<NNN>.md`. If it is missing or
   lacks required sections AND `.dev-context/auto-draft.yml` is `enabled: true`, run
   `python scripts/prd_draft.py draft {{TICKET_PREFIX}}-<NNN> --apply` to fill them via the
   generator→reviewer provider chain. Fail-soft → Blocked/Skipped, never a hard-stop.

2. **Design check** (if PRD scope touches frontend files AND no
   `## Design Spec` section): Run Phase 2.5 from `/develop` SKILL.md.
   Present via `AskUserQuestion` (Approve/Revise/Skip). **BLOCKING.**

3. **Risk/Value Assessment** (Phase 3 from `/develop`):
   - Evaluate risk (Low/Medium/High) and value (High/Medium/Low)
   - Present via `AskUserQuestion` (Proceed/Adjust scope/Stop)
   - **BLOCKING**: Must get "Proceed" for ticket to enter execution pool

4. Present final summary before spawning:
   ```
   ## Sprint Execution — Final Approval

   | Ticket | Title | Risk | Value | Decision |
   |--------|-------|------|-------|----------|
   | {{TICKET_PREFIX}}-NNN | ... | Medium | High | Proceed |

   Budget: $X remaining, est. $Y/agent = $Z total
   Agents to spawn: N
   ```
   Use `AskUserQuestion`: Execute / Remove ticket / Cancel

#### Phase C: Worktree Setup (Sequential)

For each approved ticket:

1. Create worktree + venv symlink:
   ```bash
   git fetch origin
   git worktree add ../{{PROJECT_NAME}}--{{TICKET_PREFIX}}-<NNN> \
     -b feat/{{TICKET_PREFIX}}-<NNN>-<short-desc> origin/master
   ln -s "$(pwd)/.venv" ../{{PROJECT_NAME}}--{{TICKET_PREFIX}}-<NNN>/.venv
   ```
2. Update STATUS.md Active Worktrees table (Agent = "Task Agent")
3. Update Linear → "In Progress" (fallback: `gh issue edit --add-label`)
4. Create result directory: `mkdir -p .dev-context/sprint-runs`

#### Phase D: Spawn Parallel Task Agents

**Dispatch routing** — first read the ticket's recommended model:
`python scripts/tracker.py model get {{TICKET_PREFIX}}-<NNN>`.
- If it is `external:<name>` (the external-executor rung): dispatch to the command in
  `project.conf` `EXTERNAL_EXECUTOR_<NAME>` (e.g. a GitHub App / CLI) instead of spawning
  a Claude Task. If no such command is configured, fall back to a normal Task agent on the
  effort floor and note the fallback. External executors still obey the planning gate,
  CI/review gates, and HITL merge — only the implementation step differs.
- Otherwise (`haiku`/`sonnet`/`opus`): spawn a Claude Task agent on that model.

For each approved ticket dispatched to a Claude Task, use the **Task tool** with:
- `subagent_type`: `"general-purpose"`
- `run_in_background`: `true`

**Task agent prompt**: Read the template at `references/agent-prompt-template.md` and substitute
per-ticket details (ticket ID, title, priority, acceptance criteria, worktree path, files to avoid).

#### Phase E: Report

Print summary and return control:
```
## Sprint Execution Started

Spawned N agents:
- {{TICKET_PREFIX}}-NNN: Task agent in ../{{PROJECT_NAME}}--{{TICKET_PREFIX}}-NNN (background)
- {{TICKET_PREFIX}}-NNN: Task agent in ../{{PROJECT_NAME}}--{{TICKET_PREFIX}}-NNN (background)

Use `/sprint status` to check progress.
Use `/sprint merge` when PRs are ready.
```

### Action: `status`

Report current state of all active work, including background Task agents.

1. Read STATUS.md Active Worktrees table
2. For each active worktree:
   - `git log --oneline -3` for recent commits
   - `gh pr list --head <branch>` for open PRs
   - `gh pr checks <PR>` for CI status
3. Check for sprint-run result files:
   - Read `.dev-context/sprint-runs/{{TICKET_PREFIX}}-<NNN>-result.md` for each ticket
   - Classify: SUCCESS (ready to merge), PARTIAL, BLOCKED (needs human)
3.5. **Capture sub-agent actuals** (when `SUBAGENT_LEDGER_CAPTURE=on` in `project.conf`):
   For each finished Task agent observed this round, append its duration + token usage
   to the cost-ledger so `/debrief` and the ML dataset see COMPLETE actuals — the
   SessionEnd hook only logs the MAIN session, so spawned agents are invisible without
   this. Pipe the Task tool's completion result JSON (token usage + duration) to:
   ```bash
   python scripts/ledger_append.py --ticket {{TICKET_PREFIX}}-<NNN> \
     --agent developer --session-id <task-agent-id> --result-json -
   ```
   Exactly one row per agent — **dedupe by `session_id`** (skip if a ledger row already
   carries it). Applies to PARTIAL/BLOCKED agents too (a partial run still spent time +
   tokens). Fail-soft: a capture error never blocks status.
4. Present status report:
   ```
   ## Sprint Status

   ### Completed (Ready to Merge)
   - **{{TICKET_PREFIX}}-NNN**: PR #<num> — CI passing, review approved
     - Files: N changed, M tests added

   ### In Progress
   - **{{TICKET_PREFIX}}-NNN** (feat/...): No PR yet
     - Last commit: <time ago> — "<message>"

   ### Blocked
   - **{{TICKET_PREFIX}}-NNN**: <blocker description>

   ### Merge Queue (suggested order)
   1. {{TICKET_PREFIX}}-NNN (independent, no conflicts)
   2. {{TICKET_PREFIX}}-NNN (after above, shared file: main.py)

   Run `/sprint merge` to execute merge queue.
   ```

### Action: `merge`

Merge completed PRs from the current sprint, respecting merge ordering
rules from `parallel-dev.md`.

1. Read STATUS.md Active Worktrees table
2. Collect result files from `.dev-context/sprint-runs/`
2.5. **Capture sub-agent actuals** (fallback for any agent not already captured in
   `status`; same `ledger_append.py` command + `session_id` dedupe as `status` §3.5).
   This is the authoritative last chance to record a ticket's actuals before it closes.
3. For each ticket with status=SUCCESS:
   - Verify PR exists and CI passes: `gh pr checks <PR>`
   - **Verify the `ai-code-review` status is `success` on the PR head SHA** (when
     `AI_REVIEW_GATE=on`): `gh api repos/{owner}/{repo}/commits/$SHA/status --jq
     '.statuses[]|select(.context=="ai-code-review")|.state'`. If `pending`/`failure`/
     absent (a push invalidated it via the recheck hook), re-run the in-session review
     gate (`.claude/skills/develop/references/claude-review-gate.md`) before merging.
   - Only proceed if both pass.
3.5. **Capture the review outcome** to `kpis/reviews.csv`. With the in-session AI review
   gate, the verdict is already recorded by `debrief.py --record-review` during the gate;
   for an external reviewer bot, `scripts/review_capture.py` polls for quiescence first
   (provider-agnostic):
   ```bash
   python scripts/review_capture.py --ticket {{TICKET_PREFIX}}-<NNN> --pr <PR> \
     --provider <codex|...> --owner <owner> --repo <repo> --reviewer-login "<bot[bot]>"
   # omit --owner/--repo to record finding counts without polling
   ```
   Fail-soft; never blocks the merge.
3.6. **Vis-UI gate** (advisory) — when `scripts/app_screenshot.py should_gate` is true
   (`VIS_UI_GATE=on` AND the ticket is `area:ui`), screenshot the project's routes before
   merge so a human can eyeball the UI ACs: `python scripts/app_screenshot.py --start-cmd
   "<project launch {port}>" --health-url "<...>" --base-url "<...>" --routes / ... --sha <SHA>`.
   Requires Playwright (opt-in); fail-soft + advisory — a screenshot failure never blocks.
3.7. **Rail evidence ledger** (when `RAILS_LEDGER=on`) — record the PR's `Rail evidence:`
   line into `kpis/rails.csv` so `/debrief` can report manifestation coverage
   (`.dev-context/rules/rails.md`):
   ```python
   from pathlib import Path
   import sys; sys.path.insert(0, "scripts")
   import rails
   r = rails.parse_and_append(pr_body=<PR body>, ticket="{{TICKET_PREFIX}}-<NNN>",
                              pr="<PR>", rails_csv=Path(".dev-context/kpis/rails.csv"))
   # r["flagged"] is True when the PR carries no valid Rail evidence line — surface it
   # to the human (evidence-less tickets escalate); a valid line appends a row.
   ```
   Fail-soft — a ledger error never blocks the merge.
4. Determine merge order:
   - Independent features → first-ready merges first
   - Shared file overlap → smaller change merges first
   - Explicit dependency → dependency merges first
   - Shared infra changes → **ask human** via `AskUserQuestion`
5. For each PR in order:
   a. `gh pr merge <PR> --"$(sed -n 's/^MERGE_METHOD=//p' .dev-context/project.conf | head -1)" --delete-branch` (default `merge`)
   b. Wait for CI on master: `gh run list -b master --limit 1 --json status`
   c. Remove worktree: `git worktree remove ../{{PROJECT_NAME}}--{{TICKET_PREFIX}}-<NNN>`
   d. Update STATUS.md: remove worktree row
   e. Update Linear → "Done" (fallback: `gh issue close <{{TICKET_PREFIX}}-NNN>`)
   f. Clean up result file from `.dev-context/sprint-runs/`
   g. Sync STATUS.md (idempotent): `python scripts/status_drift.py sync \
      --ticket {{TICKET_PREFIX}}-<NNN> --pr <PR> --commit <SHA>` — marks the ticket Done
      and appends an Activity Log line. Fail-soft; never blocks.
   h. Capture CI wall-clock (when `CI_LATENCY_CAPTURE=on`): `python scripts/ci_latency.py \
      --ticket {{TICKET_PREFIX}}-<NNN> --pr <PR> --sha <SHA>` → appends `kpis/ci-latency.csv`
      for `/debrief` latency tracking. Fail-soft no-op without gh/owner/repo; never blocks.
6. After all merges, trigger `/social-media {{TICKET_PREFIX}}-<NNN> --mode auto` for
   each merged ticket (non-blocking, skip on error)
7. **Emit a wave handoff** (when `HANDOFF_REVIEW=on`): `/handoff-review emit <ticket-ids>`
   creates one human-only review issue for the wave (`handoff:human-review`, excluded from
   `/sprint`). Non-blocking, fail-soft — the wave already shipped.

**Non-CLEAN merge states** (when `SPRINT_MERGE_SUPERVISOR=on`): instead of passively
waiting, delegate any PR whose `mergeStateStatus` is not CLEAN/UNSTABLE to the merge
state machine (`scripts/sprint_merge_supervisor.py`):

```bash
python scripts/sprint_merge_supervisor.py --pr <PR> --worktree <worktree-path>
```

| State | Action |
|-------|--------|
| `CLEAN` / `UNSTABLE` | `gh pr merge --$MERGE_METHOD --delete-branch` |
| `BEHIND` | rebase the worktree on `origin/master` + `git push --force-with-lease`, re-check |
| `BLOCKED` | diagnose: stale FAILURE on the same SHA → empty-commit re-trigger; else escalate (AI-review-gate / branch-protection) |
| `DIRTY` | escalate — a real merge conflict needs a human |
| `UNKNOWN` | sleep + retry (GitHub is recomputing) |

Per-PR attempt budget (default 5); `EscalateError` → stop and ask the human.

### Action: `watch [ticket-ids...]`

Resident reviewer-on-PR-open supervisor (`scripts/sprint_watch.py`, opt-in via
`SPRINT_WATCH=on`). Instead of waiting for the whole wave to finish, it polls for new
open PRs every `SPRINT_WATCH_POLL` seconds and fires a fresh-context reviewer the moment
each agent opens its PR — chaining incremental fix cycles (≤3, the same gate as
`/develop` Phase 5) and queueing each clean PR for merge via `MergeSupervisor`. Durable
JSON state (`.dev-context/sprint-watch-state.json`) lets a crashed session resume.

```bash
python scripts/sprint_watch.py --tickets <issue#…> --worktree-root .worktrees
# projects using the sibling worktree layout pass --worktree-root ..
```

The `_spawn_reviewer_task` / `_spawn_fix_task` seams are wired to the Task tool by the
orchestrator (the fresh-context reviewer per `develop/references/fresh-reviewer-prompt.md`).
`execute --watch` runs the wave with the watch loop resident.

### Action: `assign <ticket-id>`

Assign a specific ticket to a new developer agent.

1. Validate the ticket exists via `gh issue view` and is "ready"
2. Check for file conflicts with active branches
3. Create worktree and symlink venv:
   ```bash
   git worktree add ../{{PROJECT_NAME}}--{{TICKET_PREFIX}}-<NNN> origin/master
   ln -s "$(pwd)/.venv" ../{{PROJECT_NAME}}--{{TICKET_PREFIX}}-<NNN>/.venv
   ```
4. Create feature branch in the worktree
5. Update STATUS.md Active Worktrees table
6. Generate developer session prompt with:
   - Ticket details and acceptance criteria
   - Files to read first
   - Files to avoid (from other active branches)
   - Testing requirements
7. Print the prompt for the human to start a new agent session

### Action: `unblock <ticket-id>`

Investigate and resolve a blocked ticket.

1. Find the ticket in STATUS.md Active Worktrees table
2. Check the worktree for:
   - Failing tests (`pytest` output)
   - Lint/type errors (`ruff check`, `mypy`)
   - PR CI status (`gh pr checks`)
   - Merge conflicts (`git status`)
3. Propose resolution or escalate to human

## Validation

- Never assign more than 3 parallel agents
- Never assign tickets with file conflicts
- Never change ticket priority without human approval (changes sync to Linear)
- Always update STATUS.md after any assignment change
- Never spawn agents when `BUDGET_EXCEEDED` blocker exists in STATUS.md
- Always display current spend vs. budget in sprint plan output
- When spend >= 90%, suggest cheaper models (claude-haiku-4-5) for P2/P3 tickets
- When `budgets.yml` is missing, apply conservative default ($20/day) and warn human
- `execute`: All human gates (Phase B) must complete BEFORE spawning any agents
- `execute`: Task agents must NOT auto-merge — only the `merge` action handles merging
- `execute`: Verify budget can cover all agents BEFORE spawning (`remaining >= N * $10`)
- `merge`: Wait for CI on master between each merge — never merge back-to-back
- `merge`: Ask human if merge ordering is ambiguous (shared infra changes)
- `status`/`merge`: capture each finished sub-agent's actuals via `scripts/ledger_append.py` (dedupe by `session_id`) when `SUBAGENT_LEDGER_CAPTURE=on` — otherwise parallel-agent duration + token cost never reach `/debrief` or the ML dataset
- `merge`: capture the review outcome via `scripts/review_capture.py` so `reviews.csv` (and the dataset's review columns) stays populated
