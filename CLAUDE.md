# Project Context

> IMPORTANT: Prefer retrieval-led reasoning over pre-training-led reasoning.
> Always read project files, rules, and STATUS.md before making assumptions.

## Project

- **Name**: `{{PROJECT_NAME}}` — {{PROJECT_DESCRIPTION}}
- **Identifiers**: `{{PROJECT_ID}}` for decisions/branches (`{{PROJECT_ID}}-D001`, `feat/{{PROJECT_ID}}-42-foo`), `{{TICKET_PREFIX}}` for Linear issues (`{{TICKET_PREFIX}}-157`)
- **Config**: `.dev-context/project.conf`

## Stack

- **Language**: Python 3.12+ (venv at `.venv/`)
<!-- FLAVOR: Stack details filled in by setup.sh based on selected flavor -->
<!-- For fastapi-modular: FastAPI (async) + Uvicorn, PostgreSQL (SQLAlchemy 2.x async + asyncpg + Alembic), Redis (hiredis), Pydantic v2 + pydantic-settings -->
<!-- For cli: Typer + Rich -->
<!-- For basic: Pure Python -->
- **Validation**: Pydantic v2
- **HTTP**: httpx (async)

## Architecture

<!-- FLAVOR: Architecture diagram filled in after initial development -->
```
app/
├── __init__.py
└── ... (your project structure)
```

### Key Patterns

- **Singleton services**: Access via getter functions (`get_service()`) — mock at import site in tests
- **Background tasks**: `Callable[[], Coroutine]` type (not bare coroutine) — enables retry

## Commands

```bash
PYTHONPATH=. .venv/bin/pytest                    # Run all tests
PYTHONPATH=. .venv/bin/pytest tests/ -q --no-cov # Quick run without coverage
PYTHONPATH=. .venv/bin/pytest tests/unit/         # Unit tests only
ruff check --fix && ruff format                   # Lint + format
mypy --strict app/                                # Type check
pre-commit run --all-files                        # Full pre-commit suite
bash tests/hooks/test_log_session_cost.sh         # Budget review hook tests
```

## Development Workflow (Mandatory)

> **CRITICAL**: For ANY development task — feature, bug fix, refactor, performance improvement —
> use the appropriate entry point. Never skip phases within a tier unless the human approves.
>
> - New feature idea → `/develop <describe the idea>` (Feature tier — full pipeline)
> - Existing ticket → `/develop {{TICKET_PREFIX}}-NNN` (auto-detects tier from labels)
> - Bug fix → `/develop fix {{TICKET_PREFIX}}-NNN` (Fix tier — skip brainstorm/PRD)
> - Small change → `/develop tweak <desc>` (Tweak tier — minimal ceremony)
> - Production emergency → `/hotfix {{TICKET_PREFIX}}-NNN` (5-phase fast path)
> - Production health → `/monitor` (read-only diagnostics)
> - Debug investigation → `/diagnose <error>` (root cause analysis, no code changes)
> - Post-sprint calibration → `/debrief` (learn estimate factors + model routing from real actuals)
> - Resume interrupted work → `/develop resume {{TICKET_PREFIX}}-NNN`
> - Review + PR only → `/develop review {{TICKET_PREFIX}}-NNN`
> - Post-merge cleanup → `/develop cleanup {{TICKET_PREFIX}}-NNN`
>
> If the user describes a feature without invoking `/develop`, remind them of this workflow.

## Session Protocol

1. **On start**: Read `STATUS.md`, `.dev-context/DECISIONS.md`, and **`.claude/cc10x/patterns.md`** (known gotchas) before writing code. The SessionStart hook surfaces patterns + current focus.
2. **On end**: Update `STATUS.md` and **`.claude/cc10x/activeContext.md`** (current focus, learnings); append durable lessons to `.claude/cc10x/patterns.md`
3. **Before architectural choices**: Check `DECISIONS.md` — don't re-litigate accepted decisions
4. **New decisions**: Add entry to `DECISIONS.md` before implementing
5. **Task references**: Use `{{TICKET_PREFIX}}-NNN` format in commits, branches, STATUS.md
6. **Planning gate (HARD STOP)**: Never code a ticket until `python scripts/tracker.py ready <TICKET>` passes (estimate + model stamped via `/prd`). See `rules/planning-gate.md`.

## Closed Learning Loop

Every ticket carries an **AI wall-clock estimate**, a **cheapest-sufficient model**
(`haiku`/`sonnet`/`opus`), and **typed labels** (`effort`/`milestone`/`risk`/`area`;
see `rules/labeling.md` + `.dev-context/planning/taxonomy.yml`), stored canonically in
`.dev-context/kpis/estimates.csv` (17 typed columns; tracker-agnostic —
`TRACKER_BACKEND` in `project.conf` only mirrors outward).
`/prd` stamps them (`scripts/estimator.py`); `/develop` enforces the gate; `/debrief`
calibrates from real `duration_sec` actuals (`scripts/debrief.py` →
`calibration.json` + `model-policy.json`, learning per `type:`/`label:effort:`/
`label:risk:`/`label:area:`) and fits the lemmings simulator priors (`lemmings fit`).

Actuals are captured from the main session (SessionEnd hook) **and** from spawned
sub-agents (`scripts/ledger_append.py`); review outcomes via `scripts/review_capture.py`.
Each `/debrief` also emits the **ML-ready** `.dev-context/kpis/dataset.csv` — one tidy
row per ticket (typed-label features + measured outcomes) — with a generated
`FEATURES.md` data dictionary (`scripts/dataset.py`). Run `/debrief` after each sprint
to close the loop.

## Git Workflow

- **Default branch**: `master`
- **Branch from**: `master`
- **Branch naming**: `feat/{{TICKET_PREFIX}}-<number>-<short-desc>` or `fix/{{TICKET_PREFIX}}-<number>-<short-desc>`
- **Commits**: Conventional format — `feat({{TICKET_PREFIX}}-157): add response time optimization`
- **Sign-off**: All commits MUST use `--signoff` — `Signed-off-by: Alex Spivakovsky <alex.spivakovsky@gmail.com>`
- **Worktrees**: Every feature gets `git worktree add` — see parallel-dev rules
- **PR workflow**: Open PR → poll checks → auto-merge if green → ask user if red

## Rules

All rules in `.dev-context/rules/` are loaded automatically. Key files:

- `general.md` — Code quality limits (30-line functions, 200-line modules, 3 params max), naming, logging
- `git.md` — Conventional commits, branching, pre-commit hooks, commit hygiene
- `python.md` — FastAPI patterns, SQLAlchemy async, Pydantic v2, `from __future__ import annotations`
- `security.md` — Auth, input validation, SQL injection prevention, CORS
- `testing.md` — pytest-asyncio auto mode, mock strategy, Mandrake testing, 80% coverage
- `parallel-dev.md` — Worktree inventory, sync protocol, merge ordering, migration conflicts
- `planning-gate.md` — HARD STOP: no coding a ticket until it's estimated + model-routed (`tracker.py ready`)
- `labeling.md` — ML-ready typed ticket labels (effort/milestone/risk/area) + `taxonomy.yml` extension point
- `iteration-gate.md` — HARD STOP: only code a tracked, in-iteration ticket (`ITERATION_GATE`)
- `verify-claim.md` — Advisory pre-PR guard: trace data sources on relabels + new warnings
- `rails.md` — Rail R/U manifestation contract: every merged ticket leaves evidence (`RAILS_LEDGER`)

## Agent Pipeline

This project runs an autonomous multi-agent development pipeline. See `STATUS.md` for agent status table.

- **Agent definitions**: `.dev-context/agents/` (scrum_master, developer, code_reviewer, budget_review, e2e_tester, security_architect, product_manager, handoff_manager)
- **Skills**: `.claude/skills/` (develop, sprint, code-review, release, sync-dev, prd, security-review, hotfix, monitor, diagnose, social-media, handoff, handoff-review)
- **Cost tracking**: `.dev-context/cost-ledger.csv` (16 columns, logged by SessionEnd hook + `scripts/ledger_append.py` for sub-agents)
- **Operations**: `.dev-context/agentic-operations-runbook.md`
- **Autonomous AI review gate** (`AI_REVIEW_GATE=on`): `/develop` Phase 5/6 + `/sprint merge` dispatch a fresh-context reviewer (a separate Task subagent, one tier above the author; Opus on a `SECURITY_SURFACE_GLOB` surface), fail-closed, ≤3 incremental cycles. The verdict is recorded (`debrief.py --record-review`) and posted as a PR comment + SHA-keyed `ai-code-review` commit status (`debrief.py --post-review-audit`) that the `recheck-on-push` hook keeps honest. See `.claude/skills/develop/references/claude-review-gate.md` + `fresh-reviewer-prompt.md`.
- **Sprint supervision**: `scripts/sprint_merge_supervisor.py` (`SPRINT_MERGE_SUPERVISOR=on`) is a state machine for every non-CLEAN `mergeStateStatus` (BEHIND→rebase, BLOCKED→diagnose, DIRTY→escalate); `scripts/sprint_watch.py` (`SPRINT_WATCH=off`, opt-in) is a resident loop that fires a reviewer the moment each agent opens its PR. Both drive `/sprint merge` / `/sprint watch`.
- **Harness-efficiency filter** (opt-in, `HARNESS_ROUTER=on`): `scripts/harness_router.sh` routes long CI/diff output through the Gemini CLI to condense it before it enters Claude's context, and pre-filters clean PR diffs. Fail-soft; see `GEMINI.md` + `.claude/skills/develop/references/cli-router.md`. Ledger: `kpis/cli-routing.csv` (`debrief.py --cli-routing-report`).
- **Local CI gates / hooks**: `scripts/check-signoff.sh` (commit-msg sign-off enforcement, `SIGNOFF_ENFORCE`), `scripts/pre_push_tests.sh` (fast pre-push backstop, `PRE_PUSH_TESTS`), `scripts/ci_scoped_gates.sh` (diff-scoped gates, `CI_SCOPED_GATES`), and the `recheck-on-push.sh` PostToolUse hook (`REVIEW_RECHECK`) that keeps review-staleness a property of the SHA.

## Cross-Tool Configuration

This project supports multiple AI coding tools with unified configuration:

- **Source of truth**: `.dev-context/rules/`, this file (`CLAUDE.md`)
- **Cross-tool standard**: `AGENTS.md` (read by Cursor, Codex, Antigravity)
- **Tool-specific configs**: `.cursor/rules/` (Cursor), `.antigravity/` (Antigravity)
- **Sync script**: `python scripts/sync-tool-configs.py --sync` (regenerate from source)
- **Drift check**: `python scripts/sync-tool-configs.py --check` (CI/pre-commit safe)
