# Git Rules

## Conventional Commits

Format: `<type>(<scope>): <subject>`

Types:
- `feat`: new feature (bumps minor)
- `fix`: bug fix (bumps patch)
- `refactor`: code change that neither fixes a bug nor adds a feature
- `test`: adding or updating tests
- `docs`: documentation only
- `chore`: tooling, deps, CI config
- `perf`: performance improvement

Rules:
- Subject line: imperative mood, lowercase, no period, max 72 chars
- Body: wrap at 80 chars, explain *why* not *what*
- Breaking changes: add `!` after type or `BREAKING CHANGE:` in footer

```
feat(auth): add JWT refresh token rotation

Implement automatic refresh token rotation on use.
Old refresh tokens are invalidated after single use.

BREAKING CHANGE: /auth/refresh now returns both access and refresh tokens
```

## Branching Strategy

- `master` — production-ready, protected, deploy on merge
- Feature branches: `feat/{{TICKET_PREFIX}}-<number>-<short-desc>` (e.g., `feat/{{TICKET_PREFIX}}-42-user-auth`)
- Fix branches: `fix/{{TICKET_PREFIX}}-<number>-<short-desc>` (e.g., `fix/{{TICKET_PREFIX}}-15-null-email`)
- The `{{TICKET_PREFIX}}` prefix matches Linear issue identifiers (see `project.conf`)
- Keep branches short-lived: merge within 1-3 days
- **Agentic Workflow**: For every new feature/ticket, create a **new git working tree** (`git worktree add ...`) ensuring the directory name corresponds to the feature/ticket. This enables parallel agentic work
- **Parallel Dev**: When multiple agents work simultaneously, follow the full protocol in `parallel-dev.md` -- maintain the Active Worktrees table in `STATUS.md`, rebase daily, and use `/sync-dev` before merging
- **Active Rule**: Every new feature or fix must be implemented on a separate branch. Do not commit directly to `master`.

### Enforcement (3 layers)

1. **GitHub branch protection** (server-side): `master` requires PRs with passing CI (`lint-and-type-check` + `test`). Direct pushes rejected. Force-push disabled.
2. **Pre-commit hook** (local): `no-master-commit` hook aborts any commit on `master`/`main`.
3. **Pipeline validation** (agent-side): Developer agent pushes only to `feat/{{TICKET_PREFIX}}-*` or `fix/{{TICKET_PREFIX}}-*` and opens PR via `gh pr create`.

## Workflow

1. Branch from `master`
2. Make small, focused commits (one logical change per commit)
3. Rebase on `master` before PR (no merge commits in feature branches)
4. PR requires: passing CI + AI code review approval
5. **PR Submission and Review**:
    - Open PR (`gh pr create`).
    - Poll checks (`gh pr checks <PR> --watch`).
    - If checks fail: Fix and push.
6. **AI Code Review Gate**: After CI passes, the AI code reviewer
   (`.github/workflows/ai-code-review.yml`) posts a structured review:
    - Read the review comment (`gh api repos/{owner}/{repo}/issues/{PR}/comments`).
    - If verdict is **PASS** (0 violations): Proceed to merge.
    - If verdict is **FAIL** (violations found):
      a. Assess each violation -- fix genuine rule violations.
      b. For documented exceptions (e.g., standalone scripts in `scripts/`
         may exceed 200-line limit), note the rationale in a reply comment.
      c. Push fixes. Wait for new CI + AI review cycle.
      d. Repeat until verdict is PASS or only documented exceptions remain.
    - **Do NOT auto-merge** while the AI reviewer has requested changes.
7. **Merge on Approval**: When CI passes and AI review is resolved:
    - Auto-merge (`gh pr merge <PR> --merge --delete-branch`).
    - If unresolved: Ask user for guidance.
8. Merge to `master` (`--merge --delete-branch`)

## Pre-commit Hooks

Required hooks (configured in `.pre-commit-config.yaml`):
- `no-master-commit` — block direct commits to master/main
- `ruff check --fix` — lint
- `ruff format` — format
- `mypy` — type checking (strict mode)
- `pytest` — run on pre-push (full test suite)

## Commit Sign-off

- **All commits MUST include a `Signed-off-by` trailer**: `Signed-off-by: <name> <email>`
  matching the project signer (`SIGNOFF_EMAIL` in `project.conf`, set by `setup.sh`).
- Always pass `--signoff` (or `-s`) to `git commit`
- This applies to all agents and all branches — no exceptions
- **Enforced** by the `commit-msg` hook `scripts/check-signoff.sh` (`SIGNOFF_ENFORCE=on`):
  a commit missing the trailer — or carrying a non-matching signer — is rejected.

## Commit Hygiene

- Never commit secrets, `.env` files, or `__pycache__/`
- `.gitignore` must include: `.env`, `.venv/`, `__pycache__/`, `.mypy_cache/`, `.pytest_cache/`, `*.pyc`
- One Alembic migration per feature branch, squash if needed before merge
- Tag releases: `v<major>.<minor>.<patch>` — see {{PROJECT_ID}}-DNNN for versioning policy:
  - Bump minor (+0.1) when a Linear project with **code changes** is completed
  - No tag for markdown-only projects (agent specs, skills, docs)
  - Human triggers `/release` or `workflow_dispatch` — no auto-tag on push
  - Major bumps are manual human decisions only
