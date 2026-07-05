# {{PROJECT_NAME}} — Gemini CLI Context

> This file governs the Gemini CLI's operating context when invoked non-interactively
> (`gemini -p ...`) as a harness efficiency filter. It is NOT an instruction surface
> for interactive use. Active only when `HARNESS_ROUTER=on` in `.dev-context/project.conf`.

## Role

The Gemini CLI acts as a **harness filter** in two roles:

1. **Output summarizer** — condenses long CI/diff output before it enters Claude's context.
2. **Review pre-filter** — first-pass code review on non-security PR diffs.

It is called by `scripts/harness_router.sh`. Every call is instrumented to
`.dev-context/kpis/cli-routing.csv` (see `python scripts/debrief.py --cli-routing-report`).

## Output contract

All responses from `scripts/harness_router.sh` must be **valid JSON only** — no preamble,
no markdown fences, no explanation. The caller validates JSON and falls back to Claude if
invalid.

### summarize-ci schema
```json
{"status":"pass|fail","failed_tests":[],"lint_errors":[],"type_errors":[],"summary_line":""}
```

### summarize-diff schema
```json
{"files_changed":0,"summary_bullets":[],"risk_level":"low|medium|high","summary_line":""}
```

### review-prepass schema
```json
{"verdict":"PASS|FAIL","findings":[{"severity":"P1|P2|P3","file":"","line":0,"message":""}]}
```

## Security surfaces — NEVER clear without Claude

The router enforces this automatically: any diff whose path matches
`SECURITY_SURFACE_GLOB` (`.dev-context/project.conf`) always routes to Claude
Sonnet/Opus regardless of the Gemini verdict. The portable default covers paths
containing `auth`, `secret`, `crypto`, `token`, `password`, plus `DECISIONS.md` and
`security.md`. Tune the glob per project to cover its sensitive surfaces.

## Scope boundary

**Harness meta-ops only** — summarizing CI/diff output and a review pre-pass. This is
not an application LLM-routing seam; application logic must not route through this filter.

## Project rules (summary)

All code in this repo follows `.dev-context/rules/`. For code review, read those rule
files (general, python, security, testing, git) and `.dev-context/DECISIONS.md` for the
binding constraints; flag only correctness, security, and rule violations — not style
(ruff/mypy/pytest in CI already cover those).
