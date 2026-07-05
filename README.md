# {{PROJECT_NAME}}

{{PROJECT_DESCRIPTION}}

> Bootstrapped from [dev-template](https://github.com/spivi/dev-template) — a scaffold for Python
> projects driven by an agentic Claude Code development pipeline (planning gate, tiered
> `/develop` workflow, sprint orchestration, AI code review, cost/estimate learning loop).
> This file documents what the template gives you; **replace this header block** (and
> `{{PLACEHOLDER}}` tokens throughout the repo) with your project's own identity.

## Quick Start

```bash
# 1. Configure project identity (name, ticket prefix, flavor, tracker backend)
./setup.sh

# 2. Activate environment
source .venv/bin/activate

# 3. Verify setup
PYTHONPATH=. pytest

# 4. Start developing — always through /develop, never ad hoc (see below)
```

`setup.sh` prompts for a flavor and copies it into `app/`/`pyproject.toml` — pick the one
closest to what you're building, then adapt:

| Flavor | What you get |
|--------|---------------|
| `basic` | Minimal `pyproject.toml`, no app scaffold — bring your own structure |
| `cli` | A `click`/`typer`-style `app/cli.py` entry point |
| `fastapi-modular` | Full FastAPI app (`app/core/config.py`, `app/core/database.py` async SQLAlchemy, Alembic migrations, Dockerfile, `docker-compose.yml`, Procfile) |

Everything below this point (rules, skills, agents, gates) is flavor-agnostic — it works the
same regardless of which one you pick.

## Development Workflow (mandatory)

**Never write code ad hoc.** Every change — feature, fix, tweak, or emergency — goes through a
tiered entry point so estimates, model routing, and review happen consistently:

| Action | Command |
|--------|---------|
| New feature idea | `/develop <describe the idea>` (full pipeline: brainstorm → PRD → plan → implement → review → PR) |
| Existing ticket | `/develop {{TICKET_PREFIX}}-NNN` (auto-detects tier from labels) |
| Bug fix | `/develop fix {{TICKET_PREFIX}}-NNN` (skips brainstorm/PRD) |
| Small change | `/develop tweak <desc>` (minimal ceremony) |
| Production emergency | `/hotfix {{TICKET_PREFIX}}-NNN` (5-phase fast path) |
| Production health check | `/monitor` (read-only; health/logs/deployments) |
| Debug investigation | `/diagnose <error>` (root-cause only, no code changes) |
| Post-sprint calibration | `/debrief` (learns estimate factors + model routing from real actuals) |
| Resume interrupted work | `/develop resume {{TICKET_PREFIX}}-NNN` |
| Review + PR only | `/develop review {{TICKET_PREFIX}}-NNN` |
| Post-merge cleanup | `/develop cleanup {{TICKET_PREFIX}}-NNN` |

**Planning gate (hard stop):** `/develop` refuses to write code for a ticket until it's been
estimated and model-routed via `/prd` (`python scripts/tracker.py ready <TICKET>` must pass).
See `.dev-context/rules/planning-gate.md`.

See [CLAUDE.md](CLAUDE.md) for the full session protocol, git workflow, and rule index.

## Skills (`.claude/skills/`)

Slash-command entry points, invoked directly or by the agent pipeline:

| Skill | Purpose |
|-------|---------|
| `/develop` | Tiered pipeline for all code work — feature (8-phase) / fix (5-phase) / tweak (4-phase) |
| `/hotfix` | Fast 5-phase path for critical production fixes |
| `/prd` | Generate PRDs (with threat modeling), manage roadmap, create backlog tickets |
| `/sprint` | Plan sprints, spawn parallel developer agents, manage merge ordering, track budget |
| `/debrief` | Compare estimates to actuals; calibrate model routing + lemmings priors |
| `/code-review` | Rule-compliance review against `.dev-context/rules/` |
| `/security-review` | Deep OWASP Top 10 (Web/API/LLM) analysis; runs pip-audit + bandit |
| `/ux-review` | Frontend UX/engagement anti-pattern audit |
| `/dependency-guard` | Supply-chain vetting gate for any new/upgraded dependency, any ecosystem |
| `/diagnose` | Structured root-cause debugging — investigation only, no code changes |
| `/monitor` | Read-only production health/logs/deployment diagnostics |
| `/sync-dev` | Rebase a feature branch on master, run tests, push before merge |
| `/handoff` | Save AI-session state to `STATUS.md` for switching platforms/tools |
| `/handoff-review` | Non-blocking human review issue for a merged wave of features |
| `/release` | Generate release notes from conventional commits, draft a GitHub Release |
| `/frontend-design` | Multi-tier design cascade (Gemini spec → Figma/Stitch → Claude fallback) for UI work |
| `/social-media` | Draft platform-specific social posts for a shipped feature |
| `/social-animation` | Render a browser-based demo animation from a git diff/PR |
| `/project-init` | Scaffold a *new* Python project (used internally by `setup.sh`'s flavor system) |

## Agent Pipeline (`.dev-context/agents/`)

An autonomous multi-agent development pipeline, spawned by the skills above:

| Agent | Purpose | Trigger |
|-------|---------|---------|
| Product Manager | PRD generation, roadmap analysis, backlog grooming | `/prd` |
| Scrum Master | Sprint planning, ticket assignment, merge-order enforcement, escalation | `/sprint` |
| Developer Worker | Implements one ticket on one branch, opens one PR (TDD, conventional commits) | Spawned by Scrum Master |
| Code Reviewer | Reviews every PR against `.dev-context/rules/`; approves or blocks | AI review gate (in-session, `AI_REVIEW_GATE=on`) |
| Code Fixer | Applies minimal fixes for violations the Code Reviewer flags | Spawned on reviewer block |
| Security Architect | OWASP-focused security gate on every PR | AI review gate on `SECURITY_SURFACE_GLOB` paths |
| E2E Tester | Test executor + regression detector; compares coverage to base branch | AI review gate |
| Budget Review | Reads the cost ledger; lightweight cost governance | Manual `/cost`, or Scrum Master pre-check |
| Handoff Manager | Release notes from conventional commits; computes semver bump | Merge to main, or `/release` |

The AI review gate (`AI_REVIEW_GATE=on` in `project.conf`) dispatches a fresh-context reviewer
one tier above the implementing model, fails closed, and caps at 3 incremental fix cycles. See
`.claude/skills/develop/references/claude-review-gate.md`.

## Council Review — independent multi-CLI document review

For design docs, EVRs, and milestone summaries, a second layer of scrutiny is available beyond
the single-model AI review gate: **council review** convenes independent external CLIs (`codex`
+ `antigravity`) to review the same document in parallel, with a Claude chair synthesizing their
findings through an "Architectural Methodologist" persona.

- **Trigger**: opt-in via `COUNCIL_REVIEW=on` in `project.conf`. When on, writing a plan
  (`docs/plans/*-design.md`), an EVR (`*_evr.md`), or a summary/report (`*_summary.md` /
  `*_report.md`) auto-convenes the council through a `PostToolUse` hook
  (`.claude/hooks/council-on-doc-write.sh`).
- **Engine**: a vendored, pinned clone of the third-party `hex/claude-council` plugin
  (`.dev-context/vendor/claude-council/`, tracked via `.dev-context/vendor/README.md` only — the
  clone itself is gitignored and reconstructed from the pin). Orchestrated by
  `scripts/council-review.sh`.
- **Fully fail-soft and non-blocking**: a missing member CLI is skipped; the triggering `Write`
  is never blocked; every run logs to `.dev-context/kpis/council.csv`.
- **Cost policy**: Sonnet chair by default; an Opus chair requires the explicit `--allow-opus`
  flag — never silent escalation.
- **Optional autofix** (`COUNCIL_AUTOFIX=on`): the chair drafts BLOCKER-only fixes as unified
  diffs on *copies* of the target file, appended to the report. Never applied or committed
  automatically — a human reviews and applies.
- **Requires** `codex` and `agy` (antigravity-cli) on `PATH`, both keyless/subscription-auth —
  no API keys needed. Off by default.

Both members review with a generic doc-review lens by default. To specialize the review for
your project (add domain invariants, a verdict vocabulary, or a "don't re-litigate this locked
decision" check against your own ADRs/decision log), add a small `council-context.sh` hook that
emits a prompt-prefix — without forking the shared engine. See
`.dev-context/vendor/claude-council/` for the plugin's own docs.

## Lemmings — pipeline simulator (validate orchestration without burning tokens)

The agent pipeline above is expensive to dry-run: every dress rehearsal of budget gates, retry
caps, merge ordering, or escalation paths spends real LLM tokens just to exercise
*orchestration logic*. **Lemmings** is a stochastic discrete-event simulator co-located in
[`lemmings/`](lemmings/) that models the pipeline well enough to test orchestration without
spending tokens.

### Value proposition

| Without Lemmings | With Lemmings |
|------------------|----------------|
| Tweak `scrum_master.md` budget threshold → run a real sprint to verify → ~$5–50 in tokens | Tweak `lemmings/core/budget_gate.py` → `pytest` → dozens of tests in <1s, $0 |
| Wonder if the AI-review retry loop is actually capped at 3 | Run `lemmings level review_loop --seed S` over many seeds; assert `retries_capped` invariant holds |
| Hope two concurrent PRs touching `auth.py` would serialise correctly | Run `lemmings level merge_order_conflict`; trace shows `MERGE_PLAN` reporting the conflict + serialising the merges |
| Discover budget runaway in production | Run `lemmings level budget_exhausted`; assert `no_agents_after_budget_exceeded` holds across N seeds |

### How it works

- **Single source of truth** for orchestration logic. Decision functions (`budget_gate`,
  `retry_loop`, `merge_order`, `select_ticket`, `escalation`) live in `lemmings/core/` as pure
  Python and are called by both real markdown skills and the simulator. No shadow
  implementation that drifts.
- **`LEMMINGS_MODE=sim|real`** switches between RV-driven sim agents (cheap, fast, deterministic
  via seed) and real subagent invocations. Same `World` protocol, same decision core — only the
  agent factory swaps.
- **Latent-factor priors** (`sim/latents.py`) encode coarse priors: ticket complexity/novelty,
  agent skill, daily-quality shocks. Hand-tuned defaults in `priors_default.yml`; project
  overrides via `priors.override.yml`, fitted from `cost-ledger.csv` by `/debrief`.
- **Scenarios as levels.** Each canned level is a Python module: initial backlog, chaos
  disruptors at specific clock times, and optional prior overrides. Invariants are
  property-style assertions parametrised over RNG seeds.
- **Deterministic replay.** Every run is reproducible from `(scenario, seed)`. The trace
  recorder emits structured JSONL so failures can be inspected offline.

### Quick start

```bash
pip install -e ./lemmings[dev]

lemmings list                                            # canned scenarios
lemmings level budget_exhausted --seed 42 \
    --trace /tmp/trace.jsonl                             # smoke run
pytest lemmings/tests/                                    # simulator's own test suite
```

See [`lemmings/README.md`](lemmings/README.md) for architecture details and current milestone
status.

## Feature Gates (`.dev-context/project.conf`)

Most gates default **on** (safety/quality properties) or **off** (opt-in heavier machinery).
All are fail-soft — a disabled dependency (missing CLI, no tracker configured, etc.) degrades
gracefully rather than breaking your workflow. Skim `project.conf`'s inline comments for the
full explanation of each; the ones most worth knowing about on day one:

| Gate | Default | What it does |
|------|---------|---------------|
| `TRACKER_BACKEND` | `none` | `none` \| `linear` \| `github_projects` — estimates always live in `kpis/estimates.csv`; this only controls outward mirroring |
| `ITERATION_GATE` | `on` | Hard-stops `/develop`/`/sprint` on no-ticket / out-of-iteration / scope-break work |
| `AI_REVIEW_GATE` | `on` | Fresh-context AI code review on every PR, fail-closed, ≤3 fix cycles |
| `SIGNOFF_ENFORCE` | `on` | Requires a `Signed-off-by` trailer on every commit |
| `PRE_PUSH_TESTS` | `on` | Fast impacted-test backstop before push |
| `RAILS_LEDGER` | `on` | Every merged ticket leaves an evidence row (`kpis/rails.csv`) |
| `PRODUCTION_URL` | *(empty)* | Set this so `/monitor` doesn't have to guess your health-check endpoint |
| `HARNESS_ROUTER` | `off` | Route long CI/diff output through Gemini CLI to condense before it hits Claude's context |
| `SPRINT_WATCH` | `off` | Resident loop that fires a reviewer the moment each sprint agent opens its PR |
| `HANDOFF_REVIEW` | `off` | Emits one human-only GitHub issue per merged wave for review sign-off |
| `COUNCIL_REVIEW` / `COUNCIL_AUTOFIX` | `off` | See "Council Review" above |
| `VIS_UI_GATE` | `off` | Screenshot-gate UI routes before merge (needs Playwright) |

## Cross-Tool Configuration

The template's instructions work across Claude Code, Cursor, Codex, and Antigravity from one
source of truth:

- **Source of truth**: `.dev-context/rules/` + `CLAUDE.md`
- **Cross-tool standard**: `AGENTS.md` (auto-generated — do not edit directly)
- **Tool-specific configs**: `.cursor/rules/`, `.antigravity/rules/` (auto-generated)
- **Regenerate after editing rules/CLAUDE.md**: `python scripts/sync-tool-configs.py --sync`
- **Drift check** (CI/pre-commit safe): `python scripts/sync-tool-configs.py --check`

## Project Structure

```
{{PROJECT_NAME}}/
├── app/                          # Application source (shape depends on chosen flavor)
├── tests/                        # Test suite
├── scripts/                      # Automation: tracker, estimator, debrief, sync, ledger, gates
├── lemmings/                     # Pipeline simulator (token-free orchestration tests)
├── flavors/                      # basic / cli / fastapi-modular — applied once by setup.sh
├── docs/                         # Design docs, ADR-style specs
├── .dev-context/                 # Development context (tracker-agnostic, git-tracked)
│   ├── rules/                    # Code quality, security, testing, git, planning-gate rules
│   ├── agents/                   # Agent definitions (see Agent Pipeline above)
│   ├── kpis/                     # estimates.csv, dataset.csv, rails.csv, council.csv, ...
│   ├── vendor/                   # Vendored third-party plugins (council engine); pins only
│   └── project.conf              # Feature gates (see Feature Gates above)
├── .claude/                      # Claude Code configuration
│   ├── hooks/                    # SessionStart/SessionEnd/PostToolUse lifecycle hooks
│   └── skills/                   # Slash-command skills (see Skills above)
├── .cursor/, .antigravity/       # Auto-generated cross-tool mirrors — do not edit directly
├── .github/workflows/            # CI/CD, weekly dependency audit, release notes
├── CLAUDE.md                     # Project instructions (source of truth for Claude Code)
├── AGENTS.md                     # Auto-generated cross-tool instructions
├── STATUS.md                     # Current project status, active worktrees, session log
└── setup.sh                      # One-time interactive project bootstrapper
```

## Commands

```bash
PYTHONPATH=. .venv/bin/pytest                    # Run all tests
PYTHONPATH=. .venv/bin/pytest tests/ -q --no-cov # Quick run without coverage
ruff check --fix && ruff format                   # Lint + format
mypy --strict app/                                # Type check
pre-commit run --all-files                        # Full pre-commit suite
python scripts/tracker.py ready <TICKET>          # Check the planning gate for a ticket
python scripts/sync-tool-configs.py --sync        # Regenerate AGENTS.md / Cursor / Antigravity
```

## Forking This Template

1. Run `./setup.sh` — configure project identity, pick a flavor, initialize git + pre-commit.
2. Replace this README's header and `{{PLACEHOLDER}}` tokens across the repo with your project's
   real identity (`grep -rl '{{' --include='*.md'` to find the rest).
3. Read `STATUS.md` → `Next Steps` for the very first actions (create a ticket, run `/prd`,
   plan a sprint).
4. Everything under `.dev-context/rules/` is meant to be edited — it's *your* project's
   conventions, seeded with sensible Python/FastAPI defaults. Prune or extend freely; skills and
   agents read these files at runtime rather than hardcoding conventions.
5. Feature gates in `.dev-context/project.conf` are safe to leave at their defaults; turn on the
   opt-in ones (harness router, sprint watch, council review, handoff-review) only once you
   understand what they add — see "Feature Gates" above.

## Created From

This project was bootstrapped from [dev-template](https://github.com/spivi/dev-template).
