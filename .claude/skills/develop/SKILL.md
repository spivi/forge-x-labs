---
name: develop
description: "Tiered development pipeline for all code work: feature (full 8-phase), fix (medium 5-phase), tweak (light 4-phase). Single entry point that routes to appropriate ceremony level. Use when: /develop, implement, build, code, feature, fix, new ticket, build feature, fix bug, make change. Actions: <idea> (feature), fix <ticket> (fix tier), tweak <desc> (tweak tier), <ticket> (auto-detect), resume/review/cleanup <ticket>."
---

# Develop Skill (Tiered Pipeline)

Single entry point for all development work. Routes to the appropriate tier
based on the nature of the change.

**CRITICAL**: Follow phases in order. Never skip within a tier unless
the human explicitly approves the deviation.

## Tier System

| Tier | When | Phases | Human Gates |
|------|------|--------|-------------|
| **Feature** | New capability, significant change | 1→2→[UX opinion]→3→4→5→6→7→[8] | PRD approval, Risk assessment |
| **Fix** | Bug fix, regression, non-trivial fix | 3-lite→4→5→6→7 | Scope confirmation |
| **Tweak** | Small improvement, config, docs, typo | 4→5-lite→6→7 | None |

For emergencies (production down, P0): use `/hotfix` instead.

## Action Routing

| Action | Tier | Phases |
|--------|------|--------|
| `/develop <idea>` — new idea | Feature | 1 → 2 → [UX] → 3 → 4 → 5 → 6 → 7 → [8] |
| `/develop {{TICKET_PREFIX}}-NNN` — existing ticket | Auto-detect | Check labels: `type:bug`→Fix, `type:feature`→Feature, else→Fix |
| `/develop fix {{TICKET_PREFIX}}-NNN` — explicit fix | Fix | 3-lite → 4 → 5 → 6 → 7 |
| `/develop tweak <desc>` — small change | Tweak | 4 → 5-lite → 6 → 7 |
| `/develop resume {{TICKET_PREFIX}}-NNN` | (preserved) | Resume from last completed phase |
| `/develop review {{TICKET_PREFIX}}-NNN` | (preserved) | 5 → 6 → 7 |
| `/develop cleanup {{TICKET_PREFIX}}-NNN` | (preserved) | 7 |

**Auto-detect logic** for `/develop {{TICKET_PREFIX}}-NNN`:
1. Read ticket labels (`gh issue view <NNN> --json labels`)
2. If `type:bug` or `type:fix` → Fix tier
3. If `type:feature` or `type:enhancement` → Feature tier
4. If scope estimate ≤ 2 files and no `type:` label → Fix tier
5. Default → Fix tier (safer to start light; escalate if needed)

For `resume`: check `STATUS.md` Active Worktrees table for current status.
If status is `in-progress` → resume at Phase 4. If `pr-open` → resume at Phase 6.
If no worktree exists → resume at Phase 3.

---

# Feature Tier

Full pipeline for new capabilities and significant changes.

## Phase 0: Iteration Gate (all tiers)

Before any tier proceeds, apply the **iteration gate** (`.dev-context/rules/iteration-gate.md`),
governed by `ITERATION_GATE` in `project.conf`. HARD-STOP and `AskUserQuestion` when:

1. **No ticket** — the work has no tracked ticket.
2. **Out of iteration** — the ticket exists but is not in the current iteration.
3. **Scope break** — the work exceeds the ticket's stated scope / acceptance criteria.

Never claim an issue labeled `handoff:human-review` — treat it exactly like "no ticket".
Strength scales with `TRACKER_BACKEND`: enforced under `linear`/`github_projects`, advisory
(judgment-based) under `none`. Re-assert at the Phase 4 prerequisites before a worktree is created.

## Phase 1: Brainstorm (Feature only)

1. **Read context** (mandatory, in order):
   - `.dev-context/project.conf` → project ID
   - `STATUS.md` → current phase, active worktrees, blockers
   - `DECISIONS.md` → architectural constraints (check for conflicts)
   - Ticket backlog: Linear MCP `list_issues` (team filter: ALE) → verify idea isn't already tracked. Fallback: `gh issue list` if Linear MCP unavailable

2. **Explore the idea** — consider from multiple angles:
   - User value, technical feasibility, risks, alternatives
   - Identify affected modules and existing patterns to reuse
   - Consider edge cases and failure modes

3. **Output** a structured brainstorm summary:
   ```
   ## Brainstorm: <idea title>
   ### Recommended Approach
   <1-2 paragraphs>
   ### Affected Modules
   - <module>: <what changes>
   ### Reuse Opportunities
   - <existing pattern/function that can be leveraged>
   ### Risks
   - <risk>
   ### Open Questions
   - <question for PRD phase>
   ```

4. Flow directly into Phase 2 (no human gate).

---

## Phase 2: PRD (Feature only)

Generate a PRD following the template from `.claude/skills/prd/SKILL.md`.

1. **Analyze feasibility**:
   - Scan codebase for affected modules and files
   - Check existing abstractions — extend vs. create new
   - Review related test files for existing coverage
   - Estimate complexity: S (1-2 files), M (3-5 files), L (6+ files)

2. **Generate PRD** with all sections:
   - Problem Statement, Proposed Solution, Acceptance Criteria
   - Scope Estimate (files table), Risks, Dependencies, Alternatives
   - **Threat Model** (per `.dev-context/agents/security_architect.md`):
     OWASP Web Top 10, API Top 10, LLM Top 10 (only relevant categories)

3. **Human gate** — MUST use `AskUserQuestion` tool:
   - First, output the full PRD with threat model as text
   - Then call `AskUserQuestion` with these exact options:
     - "Approve" → create GitHub Issue + proceed
     - "Revise" → wait for feedback, then regenerate
     - "Reject" → archive and stop
     - "Defer" → save to roadmap for later
   - **BLOCKING**: Do NOT proceed until the user selects "Approve"

4. **On approval** — create ticket (Linear-first):
   - **Primary** — Linear MCP `create_issue`:
     - team: ALE, title, description, priority, state: "Backlog"
   - **CRITICAL — Linear markdown formatting**:
     - Pass the `description` parameter as a **real multi-line string** with actual
       newlines, NOT escaped `\n` sequences. The MCP tool accepts multi-line strings
       natively. Escaped `\n` gets double-escaped and renders as literal `\\n` in Linear.
     - Use standard markdown: `## Headings`, `- [ ] checkboxes`, `**bold**`, `| tables |`
     - Linear auto-converts `- item` to `* item` — both are fine
     - Keep descriptions concise for Linear (summary + acceptance criteria + scope +
       dependencies). Link to the full PRD file for details: `Full PRD: \`.dev-context/prds/{{TICKET_PREFIX}}-NNN.md\``
   - **Fallback** (if Linear MCP unavailable):
     `gh issue create --title "{{TICKET_PREFIX}}-<NNN>: <title>" --body "<PRD>" --label "priority:<P>,status:ready"`
   - Save PRD: `.dev-context/prds/{{TICKET_PREFIX}}-<NNN>.md`

5. **UX opinion** — evaluate whether the feature has UX implications:
   - Scan PRD scope for frontend files (`app/templates/**`, `app/static/**`, `*.html`, `*.css`, `*.js`)
   - Also consider: does this feature change user-facing behavior even if backend-only?
     (e.g., new WhatsApp response format, different shopping flow, changed error messages)
   - If yes → proceed to UX Opinion step below
   - If purely internal (infra, refactor, tooling) → skip to Phase 3

### UX Opinion (Feature tier — lightweight, non-blocking)

A quick UX sanity check, NOT a full design spec. Takes 2 minutes, not 20.

1. **Read**: `.dev-context/design-guidelines.md` and current `app/templates/shop.html`

2. **Provide a brief UX opinion** (3-5 bullet points max):
   ```
   ## UX Opinion: {{TICKET_PREFIX}}-<NNN>
   - <How this feature affects the user experience>
   - <RTL/mobile consideration if relevant>
   - <Potential friction point or engagement risk>
   - <Suggestion for user flow>
   ```

3. **If the feature is UX-heavy** (new page, new flow, major layout change):
   - Offer: "This feature has significant UX scope. Want me to generate a full
     Design Spec before implementation?"
   - Use `AskUserQuestion`: "Generate design spec?" → Yes / No
   - If Yes: run the full design spec process (see Design Spec appendix below)
   - If No: proceed with just the UX opinion as guidance

4. **Non-blocking**: The UX opinion is guidance, not a gate. Proceed to Phase 3.

---

## Phase 3: Risk/Value Assessment

### Feature tier (full assessment)

Evaluate the ticket on two axes:

**Risk**:
- **Low**: <3 files, well-understood patterns, no security surface
- **Medium**: 3-10 files, extends existing infra, moderate complexity
- **High**: >10 files, new infrastructure, security-sensitive, external integrations

**Value**:
- **High**: User-facing feature, unblocks other work, addresses P0/P1
- **Medium**: Improves code quality, DX, or performance (P2)
- **Low**: Cosmetic, nice-to-have, minor cleanup (P3)

**Decision matrix**:

| | High Value | Medium Value | Low Value |
|---|---|---|---|
| **Low Risk** | Proceed | Proceed | Ask human |
| **Medium Risk** | Proceed | Ask human | Stop |
| **High Risk** | Ask human | Stop | Stop |

**Human gate** — MUST use `AskUserQuestion` tool:
- Output the risk/value assessment as text
- Call `AskUserQuestion` with: "Proceed" / "Adjust scope" / "Stop"
- **BLOCKING**: Do NOT proceed to Phase 4 until the user selects "Proceed"

### Fix tier (lightweight scope check — Phase 3-lite)

Lighter version — confirm scope, don't run the full matrix:

1. **Read the ticket** and identify:
   - What's broken (symptom)
   - Likely files to change (scope)
   - Security implications (auth, data, input handling?)

2. **Quick scope confirmation** via `AskUserQuestion`:
   ```
   Fix scope for {{TICKET_PREFIX}}-<NNN>: <title>
   - Files: <list of likely files>
   - Security relevant: yes/no
   - Estimated size: S/M/L
   ```
   - Options: "Proceed" / "Needs more investigation (run /diagnose)" / "Too big — escalate to feature tier"

---

## Phase 4: Implementation (Ralph Loop)

**Same for Feature and Fix tiers. Tweak tier uses a simplified version (see below).**

### Prerequisites (BLOCKING)

Before writing code, verify:
1. **Feature tier**: GitHub Issue + PRD file exist, user approved Phase 3
2. **Fix tier**: Ticket exists (or description provided), user confirmed scope
3. **Tweak tier**: No prerequisites — just go

**Planning gate (HARD STOP — Feature & Fix tiers):** the ticket MUST be estimated
and model-routed before any code:
```bash
python scripts/tracker.py ready <TICKET>   # exit 0 = launchable, exit 1 = blocked
```
If it exits non-zero, STOP and stamp it first (this is what `/prd` does automatically):
```bash
python scripts/tracker.py plan <TICKET> --type <feature|fix> --labels "effort:<S|M|L>"
```
Then mark the run started so its session ledger joins back to the estimate:
```bash
python scripts/tracker.py status set <TICKET> in_progress
```
See `rules/planning-gate.md`. (Tweak tier is exempt — minimal ceremony.)

### Setup

1. **Create worktree**:
   ```bash
   git worktree add ../{{PROJECT_NAME}}--{{TICKET_PREFIX}}-<NNN> -b feat/{{TICKET_PREFIX}}-<NNN>-<short-desc> origin/master
   ln -s "$(pwd)/.venv" ../{{PROJECT_NAME}}--{{TICKET_PREFIX}}-<NNN>/.venv
   ```
   (Fix tier uses `fix/` prefix instead of `feat/`)

2. **Update STATUS.md** — add row to Active Worktrees table

3. **Update Linear** (primary) via MCP `update_issue` → state "In Progress".
   Fallback: `gh issue edit <{{TICKET_PREFIX}}-NNN> --add-label "status:in-progress"`

### Start Ralph Loop

Invoke `/ralph-loop` with dynamically generated prompt. Read the prompt template at
`references/ralph-loop-prompt.md` and substitute the ticket details, acceptance criteria,
and worktree path.

### After Ralph Loop

Proceed to Phase 5. If exited due to max iterations or blocker,
inform the human and ask how to proceed.

---

## Phase 5: Review

### Feature and Fix tiers (full review)

When `AI_REVIEW_GATE=on` (default), the review is a **fresh-context, one-tier-stronger,
fail-closed** merge gate — NOT an author self-review:

1. **Dispatch the fresh-context review gate** per
   `.claude/skills/develop/references/claude-review-gate.md`. A *separate* Task subagent
   (one model tier above the author; Opus on a `SECURITY_SURFACE_GLOB` surface) runs both
   `/code-review` and `/security-review` on the diff and returns a structured JSON verdict.
   The author does NOT review their own diff.
2. **If frontend files changed**: run `/ux-review` (BLOCK findings fixed before PR).
3. **Incremental fix → re-review** (≤ 3 cycles): fix P1 (+ in-budget P2) minimally,
   re-dispatch the reviewer on ONLY the new delta; still-P1 after 3 cycles → escalate to
   the human, do NOT merge.
4. **Verify-claim self-cert** (`.dev-context/rules/verify-claim.md`): if the diff relabels a
   reported value **or** adds a new warning/log line, trace the data source and add the
   `Claim verified:` line(s) to the PR body.
5. **Update Linear** → state "In Review".

(When `AI_REVIEW_GATE=off`: fall back to author-context `/code-review` + `/security-review`
on the changed files, max 3 fix cycles.)

### Tweak tier (Phase 5-lite — lightweight review)

1. **Run `/code-review`** on changed files only
2. **Skip `/security-review`** unless the change touches auth, input handling, or data storage
3. **Skip `/ux-review`** unless the change is specifically a frontend tweak
4. **Max 1 review-fix cycle** — if it still fails, note in PR and proceed

---

## Phase 6: PR + Merge

### PR Creation

1. **Push branch**:
   ```bash
   git push -u origin feat/{{TICKET_PREFIX}}-<NNN>-<short-desc>
   ```

2. **Open PR**:
   ```bash
   gh pr create --title "feat({{TICKET_PREFIX}}-<NNN>): <title>" --body "$(cat <<'EOF'
   ## Summary
   <1-3 bullet points>

   ## Ticket
   {{TICKET_PREFIX}}-<NNN>

   ## Test Plan
   - [ ] <acceptance criterion 1>
   - [ ] <acceptance criterion 2>

   ## Tier
   Feature / Fix / Tweak

   Rail evidence: R — <one-line measurable claim>   # or: U — <UI-surface claim>

   Generated with [Claude Code](https://claude.com/claude-code)
   EOF
   )"
   ```
   The `Rail evidence:` line is **required** (`.dev-context/rules/rails.md`) — Rail R for a
   measurable delta, Rail U for a user-facing surface. `/sprint merge` records it into
   `kpis/rails.csv`; a PR with no valid line is flagged for human attention.

3. **Update STATUS.md** — worktree row status → `pr-open`

### Merge Lifecycle

4. **Poll CI**: `gh pr checks <PR> --watch`
5. **If CI fails**: read failure, fix, push, re-poll (up to 3 iterations)
6. **Read the AI review gate status** (the SHA-keyed commit status set in Phase 5 step 5,
   via `debrief.py --post-review-audit`):
   ```bash
   SHA=$(gh pr view <PR> --json headRefOid --jq .headRefOid)
   gh api repos/{owner}/{repo}/commits/$SHA/status \
     --jq '.statuses[] | select(.context=="ai-code-review") | .state'
   ```
7. **If the status is `pending`/`failure` or absent**: a push changed the SHA (the
   `recheck-on-push` hook flips it to `pending`) — re-run the incremental review gate
   (Phase 5 step 3), then re-post the audit. Up to 3 cycles.
8. **When CI passes AND `ai-code-review` = `success` on the head SHA**, merge with the
   configured method (`MERGE_METHOD` in `project.conf`, default `merge`):
   ```bash
   METHOD=$(sed -n 's/^MERGE_METHOD=//p' .dev-context/project.conf | head -1)
   gh pr merge <PR> --"${METHOD:-merge}" --delete-branch
   ```
9. Proceed to Phase 7.

**If merge blocked after 3 CI/review cycles**: stop and ask human.

---

## Phase 7: Deploy Verification & Cleanup

After successful merge:

1. **Wait for Railway deployment**:
   - Poll `mcp__railway-mcp-server__list-deployments` (service: "web", environment: "production")
   - Verify health: `curl -sf <health-endpoint>`
   - If deployment fails: print logs, STOP, alert human

2. **Cleanup**:
   - Remove worktree: `git worktree remove ../{{PROJECT_NAME}}--{{TICKET_PREFIX}}-<NNN>`
   - Update STATUS.md — remove worktree row
   - Update Linear → state "Done"

3. **Print summary**:
   ```
   ## Development Complete: {{TICKET_PREFIX}}-<NNN>
   - PR: #<number> (merged)
   - Tier: Feature / Fix / Tweak
   - Deployed: Railway production
   - Health: OK
   ```

4. **Feature tier only** — offer social media:
   - Print: "Feature deployed. Run `/social-media {{TICKET_PREFIX}}-<NNN>` if you want to announce it."
   - Do NOT auto-invoke. The human decides.

---

# Tweak Tier (Minimal Pipeline)

For small improvements that don't need ceremony.

## Tweak Phase 4: Implementation (Simplified)

1. **Create branch** (worktree still recommended for clean isolation):
   ```bash
   git worktree add ../{{PROJECT_NAME}}--tweak-<short-desc> -b fix/{{TICKET_PREFIX}}-<NNN>-<short-desc> origin/master
   ln -s "$(pwd)/.venv" ../{{PROJECT_NAME}}--tweak-<short-desc>/.venv
   ```

2. **Make the change** — no Ralph Loop needed for tweaks:
   - Apply the change directly
   - Run validation: `ruff check . --fix && ruff format . && PYTHONPATH=. pytest tests/ -q --no-cov`
   - Commit with conventional format

3. Proceed to Phase 5-lite → Phase 6 → Phase 7.

---

## Sprint Agent Mode

When invoked by a Task agent spawned from `/sprint execute`:

- **Phases 1-3 are pre-completed**: Sprint orchestrator handled PRD and gates
- **Phase 6 does NOT auto-merge**: Creates PR, leaves merge to `/sprint merge`
- **Phase 7 deferred**: Cleanup handled by sprint orchestrator
- **No `AskUserQuestion` calls**: Fully autonomous
- **Result file**: Agent writes to `.dev-context/sprint-runs/{{TICKET_PREFIX}}-<NNN>-result.md`

---

## Validation Rules

- **Never skip phases within a tier** without explicit human approval
- **Tier selection is flexible**: If a fix turns out to be bigger than expected,
  say "This needs the Feature tier" and escalate. Don't force a complex change
  through the Fix pipeline
- **Human gates use `AskUserQuestion`** — Feature tier Phase 2 and Phase 3
  gates MUST use the tool, not just text output
- **Never use `--no-verify`** on git commits
- **Never auto-merge** if AI Code Review verdict is FAIL
- **Always create a worktree** for implementation
- **Always use Linear MCP as primary** for ticket operations, `gh` CLI as fallback
- **Always update STATUS.md** Active Worktrees when creating/removing worktrees
- **Always save PRDs** to `.dev-context/prds/` for traceability
- If budget is exceeded (STATUS.md `BUDGET_EXCEEDED` blocker), refuse Phase 4
- If the user describes a feature without invoking `/develop`, remind them
  of this workflow and offer to start it

---

## Appendix: Full Design Spec (Opt-In)

Only generated when explicitly requested. See `references/design-spec.md` for the full process.
