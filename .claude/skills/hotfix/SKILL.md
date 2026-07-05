---
name: hotfix
description: "Fast 5-phase path for critical production fixes. Bypasses brainstorm, PRD, and risk assessment. Use when: /hotfix, urgent fix, P0 bug, production down, service broken, users affected, data at risk, emergency fix. For non-urgent bugs, use /develop fix instead."
---

# Hotfix Skill (Emergency Fast Path)

Expedited pipeline for critical production fixes. Skips brainstorm, PRD, design,
risk assessment, and social media. Gets a fix deployed as fast as safely possible.

## Phases

Only 5 phases (vs 8 in the full pipeline):

```
Triage → Implement → Review → PR+Merge → Deploy Verify
```

---

## Phase 1: Triage

1. **Read context** (fast — skip deep exploration):
   - `STATUS.md` — check for active worktrees, blockers
   - If `{{TICKET_PREFIX}}-NNN` provided: read the ticket (`gh issue view` or Linear MCP)
   - If description provided: skip ticket lookup, work from the description

2. **Assess the issue**:
   - What's broken? (user-facing impact)
   - What's the likely root cause? (1-2 candidate modules)
   - Is a rollback faster than a fix? If yes, suggest rollback first

3. **Quick output** (no gate — inform and proceed):
   ```
   ## Hotfix Triage: <issue>
   - Impact: <what's broken for users>
   - Likely cause: <module(s)>
   - Approach: <1-sentence fix strategy>
   - Rollback viable: yes/no
   ```

---

## Phase 2: Implement

### Setup

1. **Create branch** (worktree for consistency):
   ```bash
   git fetch origin
   git worktree add ../{{PROJECT_NAME}}--hotfix-<short-desc> -b fix/{{TICKET_PREFIX}}-<NNN>-<short-desc> origin/master
   ln -s "$(pwd)/.venv" ../{{PROJECT_NAME}}--hotfix-<short-desc>/.venv
   ```

2. **Update STATUS.md** — add row to Active Worktrees table

### Fix

3. **Write a regression test** that reproduces the bug (TDD — test must fail first)
4. **Apply the minimal fix** — smallest change that resolves the issue
   - Follow code rules (type annotations, 30-line functions, etc.)
   - Do NOT refactor surrounding code — fix only
5. **Verify**:
   ```bash
   ruff check . --fix && ruff format .
   PYTHONPATH=. .venv/bin/pytest tests/ -q --no-cov
   ```
   - Full coverage check not required for hotfixes — just ensure no regressions
   - If mypy or pre-commit are fast enough, run them too

---

## Phase 3: Review (Lightweight)

1. **Run `/code-review`** on changed files only
2. **If the fix touches auth, input handling, or data storage**:
   run `/security-review` on changed files
3. **Skip `/ux-review`** unless the fix is specifically about a frontend rendering bug
4. **Max 1 review-fix cycle** — if it fails twice, push anyway and note in PR

---

## Phase 4: PR + Merge

### PR Creation

1. **Push branch**:
   ```bash
   git push -u origin fix/{{TICKET_PREFIX}}-<NNN>-<short-desc>
   ```

2. **Open PR**:
   ```bash
   gh pr create --title "fix({{TICKET_PREFIX}}-<NNN>): <description>" --body "$(cat <<'EOF'
   ## Hotfix

   **Impact**: <what was broken>
   **Root cause**: <1 sentence>
   **Fix**: <1 sentence>

   ## Test Plan
   - [ ] Regression test added
   - [ ] Existing tests pass

   HOTFIX — expedited review requested.
   EOF
   )"
   ```

3. **Update STATUS.md** — worktree row status → `pr-open`

### Merge Lifecycle

> **CRITICAL**: Execute ALL steps below automatically without pausing for
> human input. The agent drives the full loop: poll → read review → fix →
> re-poll → merge. Only stop on hard failures after max retries.

4. **Poll CI**: `gh pr checks <PR> --watch`
5. **If CI fails**: read failure, fix, push, re-poll (up to 2 iterations)
6. **Read AI Code Review**: `gh api repos/{owner}/{repo}/issues/{PR}/comments`
7. **If AI review has violations**: assess each violation — fix genuine rule
   violations, note documented exceptions in a reply comment. Push fixes,
   wait for new review cycle (max 1 cycle for hotfix).
8. **When CI passes AND AI review is PASS (or no violations)**:
   ```bash
   gh pr merge <PR> --merge --delete-branch
   ```
9. **If CI fails on unrelated tests**: merge anyway if the hotfix tests pass
   and the failure is pre-existing. Note in PR comment.

**If merge blocked after 2 CI or 1 review cycle**: stop and ask human.

---

## Phase 5: Deploy Verify + Cleanup

1. **Wait for Railway deployment** (same as `/develop` Phase 7):
   - Poll `mcp__railway-mcp-server__list-deployments` or `railway status --json`
   - Verify health: `curl -sf <health-endpoint>`

2. **If deployment fails**: print logs, STOP, alert human

3. **Cleanup**:
   - Remove worktree: `git worktree remove ../{{PROJECT_NAME}}--hotfix-<short-desc>`
   - Update STATUS.md — remove worktree row
   - Update Linear/GitHub — close ticket or mark done

4. **Print summary**:
   ```
   ## Hotfix Deployed: {{TICKET_PREFIX}}-<NNN>
   - PR: #<number> (merged)
   - Fix: <1 sentence>
   - Deployed: Railway production
   - Health: OK
   - Time: <minutes from start to deploy>
   ```

---

## What this skill does NOT do

- No brainstorm phase
- No PRD generation
- No design spec
- No risk/value assessment
- No social media
- No full coverage check (just regression test + no regressions)
- No 3-cycle review loop (max 1 cycle)

## When to escalate back to /develop

If during triage you realize the fix requires:
- New infrastructure or architecture changes
- Touching >5 files
- Database migration
- Breaking API changes

Then stop and say: "This isn't a hotfix — it needs `/develop fix {{TICKET_PREFIX}}-NNN`."
