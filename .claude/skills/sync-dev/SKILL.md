---
name: sync-dev
description: "Sync feature branch with master before merge. Rebases on origin/master, runs full test suite, pushes with --force-with-lease. Use when: /sync-dev, sync with master, pre-merge sync, rebase master, update branch, pull latest. Modes: check (dry-run) or full (rebase + test + push)."
---

# Sync Dev Skill

Synchronize the current feature branch with `master` following the parallel
development protocol. Use before merging or when starting a new session.

## Instructions

### Step 0 — Validate Context

1. Confirm you are on a feature branch (not `master` or `main`)
2. Read the **Active Worktrees** table in `STATUS.md`
3. Identify which files other active branches are touching

### Step 1 — Fetch & Assess

```bash
git fetch origin
git log --oneline HEAD..origin/master
```

Report to the user:
- Number of new commits on `master` since the branch diverged
- Whether any of those commits touch files this branch also modifies
- Risk level: **low** (no overlap), **medium** (some shared files),
  **high** (same files modified by both)

If `mode` is `check`, stop here and report. Otherwise continue.

### Step 2 — Rebase

```bash
git rebase origin/master
```

- **Clean rebase**: Proceed to Step 3
- **Conflicts**: List each conflicted file with context. For each:
  - If the conflict is in a file only this branch modifies: resolve it
  - If the conflict is in a shared file: show both sides to the user
    and ask how to resolve
  - If >3 files conflict: stop and ask the user for guidance

### Step 3 — Verify

Run the full verification suite:

```bash
# Tests
PYTHONPATH=. .venv/bin/pytest

# Lint + format + type check
pre-commit run --all-files
```

- If everything passes: proceed to Step 4
- If tests fail: investigate whether the failure is from the rebase
  (regression) or pre-existing. Report findings to user

### Step 4 — Push

```bash
git push --force-with-lease origin HEAD
```

`--force-with-lease` is mandatory (never bare `--force`). This ensures
we don't overwrite commits someone else pushed to this branch.

### Step 5 — Update STATUS.md

Update the **Active Worktrees** table:
- Refresh the "Files Touched" column with current file list
- Update "Status" to reflect sync state

## Output Format

```markdown
## Sync Report: <branch-name>

**Commits behind master**: N
**File overlap with other branches**: [list or "none"]
**Risk level**: low / medium / high

### Rebase Result
- [Clean / N conflicts resolved / Blocked — needs user input]

### Verification
- Tests: PASS / FAIL (N failures)
- Pre-commit: PASS / FAIL (details)

### Push
- [Pushed / Skipped — verification failed]

### Active Worktrees (updated)
| Branch | Worktree Dir | Ticket | Agent | Status | Files Touched |
|--------|-------------|--------|-------|--------|---------------|
| ... | ... | ... | ... | ... | ... |
```

## Validation

- Verify you are NOT on `master` or `main`
- Verify `--force-with-lease` was used (never bare `--force`)
- Verify tests pass after rebase before pushing
- Verify STATUS.md Active Worktrees table is updated
